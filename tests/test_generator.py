import json
import sqlite3
import unittest

from mathcounts_platform.db import (
    create_generated_problem,
    create_user,
    get_generated_problem,
    get_generated_problems_for_user,
    migrate,
    record_generated_check,
)
from mathcounts_platform.generator import (
    DeepSeekClient,
    GeneratorError,
    GeneratorFormatError,
    GeneratorNotConfigured,
    answers_equivalent,
    build_generation_messages,
    build_solver_messages,
    check_generated_answer,
    evaluate_answer,
    generate_similar_problem,
    load_dotenv,
    parse_json_content,
)
from mathcounts_platform.views import render_generated_list_page, render_practice_page


SOURCE = {
    "year": 2025,
    "round": "Sprint",
    "question_number": 3,
    "subject": "Geometry",
    "difficulty": "Easy",
    "page": 11,
    "summary": "Height of a box given volume length and width",
}


class FakeClient:
    """Returns scripted JSON payloads in order and records the requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat_json(self, messages, temperature, thinking=None):
        self.calls.append({"messages": messages, "temperature": temperature, "thinking": thinking})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def generated(answer="6", unit="inches"):
    return {
        "problem": "A box has volume 120 in³, length 5 in and width 4 in. What is its height?",
        "answer": answer,
        "unit": unit,
        "solution": "120 ÷ (5 × 4) = 6",
    }


class GenerateSimilarProblemTest(unittest.TestCase):
    def test_accepts_problem_when_independent_solve_agrees(self):
        client = FakeClient([generated(), {"solution": "Divide 120 by 20 to get 6.", "answer": "6"}])

        result = generate_similar_problem(SOURCE, client)

        self.assertEqual(result["answer"], "6")
        self.assertEqual(result["solution"], "Divide 120 by 20 to get 6.")
        self.assertEqual(result["unit"], "inches")
        self.assertEqual(len(client.calls), 2)
        self.assertIn(generated()["problem"], client.calls[1]["messages"][1]["content"])
        self.assertEqual(client.calls[1]["temperature"], 0.0)

    def test_rejects_problems_the_verifier_flags_as_flawed(self):
        client = FakeClient(
            [
                generated(),
                {"answer": "6", "well_posed": False, "issues": "contradictory"},
                generated(),
                {"answer": "6", "well_posed": "true"},
            ]
        )

        generate_similar_problem(SOURCE, client)

        self.assertEqual(len(client.calls), 4)

    def test_rejects_hard_target_rated_easy(self):
        hard_source = dict(SOURCE, difficulty="Hard")
        client = FakeClient(
            [generated(), {"answer": "6", "difficulty": "Easy"}, generated(), {"answer": "6", "difficulty": "Medium"}]
        )

        generate_similar_problem(hard_source, client)

        self.assertEqual(len(client.calls), 4)

    def test_solver_prompt_asks_for_review(self):
        content = build_solver_messages("What is 2+2?")[1]["content"]

        self.assertIn('"well_posed"', content)
        self.assertIn('"difficulty"', content)

    def test_falls_back_to_generator_solution(self):
        client = FakeClient([generated(), {"answer": "6"}])

        self.assertEqual(generate_similar_problem(SOURCE, client)["solution"], "120 ÷ (5 × 4) = 6")

    def test_stops_retrying_after_time_budget(self):
        ticks = iter([0, 400])
        client = FakeClient([generated(), {"answer": "7"}, generated(), {"answer": "6"}])

        with self.assertRaises(GeneratorError):
            generate_similar_problem(SOURCE, client, time_budget=300, clock=lambda: next(ticks))
        self.assertEqual(len(client.calls), 2)

    def test_retries_when_solver_disagrees_then_gives_up(self):
        client = FakeClient([generated(), {"answer": "7"}] * 3)

        with self.assertRaises(GeneratorError):
            generate_similar_problem(SOURCE, client)
        self.assertEqual(len(client.calls), 6)

    def test_retry_can_succeed(self):
        client = FakeClient([generated(), {"answer": "7"}, generated(answer="3/4", unit=""), {"answer": "0.75"}])

        result = generate_similar_problem(SOURCE, client)

        self.assertEqual(result["answer"], "3/4")

    def test_format_errors_are_retried(self):
        client = FakeClient([GeneratorFormatError("ran out of tokens"), generated(), {"answer": 6}])

        result = generate_similar_problem(SOURCE, client)

        self.assertEqual(result["answer"], "6")

    def test_generation_thinking_setting_only_applies_to_generation_call(self):
        client = FakeClient([generated(), {"answer": "6"}])
        client.generate_thinking = False

        generate_similar_problem(SOURCE, client)

        self.assertIs(client.calls[0]["thinking"], False)
        self.assertIsNone(client.calls[1]["thinking"])

    def test_prompt_describes_subject_difficulty_round_and_summary(self):
        content = build_generation_messages(SOURCE)[1]["content"]

        self.assertIn("Geometry", content)
        self.assertIn("Easy", content)
        self.assertIn("no calculator", content)
        self.assertIn("Height of a box", content)
        self.assertIn("problem 3 of 30", content)
        self.assertIn('"answer"', content)


class DeepSeekClientTest(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(GeneratorNotConfigured):
            DeepSeekClient.from_environ({})

    def test_sends_openai_compatible_request_and_parses_json(self):
        captured = {}

        def transport(url, headers, payload):
            captured.update(url=url, headers=headers, payload=payload)
            return {"choices": [{"message": {"content": json.dumps({"answer": "42"})}}]}

        client = DeepSeekClient.from_environ({"DEEPSEEK_API_KEY": "sk-test"})
        client.transport = transport

        result = client.chat_json([{"role": "user", "content": "hi"}], temperature=0.0)

        self.assertEqual(result, {"answer": "42"})
        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(captured["payload"]["model"], "deepseek-chat")
        self.assertEqual(captured["payload"]["response_format"], {"type": "json_object"})

    def test_model_and_base_url_are_configurable(self):
        client = DeepSeekClient.from_environ(
            {"DEEPSEEK_API_KEY": "k", "DEEPSEEK_MODEL": "deepseek-reasoner", "DEEPSEEK_BASE_URL": "http://x/"}
        )

        self.assertEqual(client.model, "deepseek-reasoner")
        self.assertEqual(client.base_url, "http://x")
        self.assertIsNone(client.generate_thinking)
        self.assertEqual(client.max_tokens, 8000)

    def test_thinking_toggle_and_token_limit_from_environ(self):
        captured = {}
        client = DeepSeekClient.from_environ(
            {"DEEPSEEK_API_KEY": "k", "DEEPSEEK_GENERATE_THINKING": "off", "DEEPSEEK_MAX_TOKENS": "4000"}
        )
        client.transport = lambda url, headers, payload: (
            captured.update(payload) or {"choices": [{"message": {"content": "{}"}}]}
        )

        client.chat_json([], temperature=1.0, thinking=client.generate_thinking)

        self.assertIs(client.generate_thinking, False)
        self.assertEqual(captured["max_tokens"], 4000)
        self.assertEqual(captured["chat_template_kwargs"], {"thinking": False})

    def test_empty_truncated_reply_is_a_retryable_format_error(self):
        client = DeepSeekClient("k", transport=lambda *args: {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})

        with self.assertRaises(GeneratorFormatError):
            client.chat_json([], temperature=0.0)

    def test_parse_json_content_handles_code_fences_and_rejects_garbage(self):
        self.assertEqual(parse_json_content('```json\n{"answer": "5"}\n```'), {"answer": "5"})
        self.assertEqual(parse_json_content('Sure! {"answer": "5"}'), {"answer": "5"})
        with self.assertRaises(GeneratorError):
            parse_json_content("no json here")

    def test_load_dotenv_does_not_override_existing_values(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env"
            env_path.write_text(
                '# comment\nDEEPSEEK_API_KEY="from-file # not a comment"\nexport OTHER=1\n'
                "KEEP=file\nDEEPSEEK_GENERATE_THINKING=off   # vLLM only\n"
            )
            environ = {"KEEP": "existing"}

            load_dotenv(env_path, environ)

        self.assertEqual(
            environ,
            {
                "DEEPSEEK_API_KEY": "from-file # not a comment",
                "OTHER": "1",
                "KEEP": "existing",
                "DEEPSEEK_GENERATE_THINKING": "off",
            },
        )


class AnswerEquivalenceTest(unittest.TestCase):
    def test_evaluates_common_answer_forms(self):
        self.assertAlmostEqual(evaluate_answer("2sqrt(3)"), 2 * 3 ** 0.5)
        self.assertAlmostEqual(evaluate_answer("2√3"), 2 * 3 ** 0.5)
        self.assertAlmostEqual(evaluate_answer("5pi"), 5 * 3.141592653589793)
        self.assertAlmostEqual(evaluate_answer("-3/4"), -0.75)
        self.assertEqual(evaluate_answer("1,024"), 1024)
        self.assertIsNone(evaluate_answer("__import__('os')"))
        self.assertIsNone(evaluate_answer("9**9**9"))

    def test_answers_equivalent(self):
        self.assertTrue(answers_equivalent("3/4", "0.75"))
        self.assertTrue(answers_equivalent("2sqrt(3)", "sqrt(12)"))
        self.assertTrue(answers_equivalent("(1, -3)", "(1,-3)"))
        self.assertFalse(answers_equivalent("6", "7"))
        self.assertFalse(answers_equivalent("", ""))

    def test_student_check_accepts_unit_and_equivalent_exact_forms_only(self):
        self.assertTrue(check_generated_answer("6", "6", "inches"))
        self.assertTrue(check_generated_answer("6 inches", "6", "inches"))
        self.assertTrue(check_generated_answer("2*sqrt(3)", "2sqrt(3)"))
        self.assertTrue(check_generated_answer("2√3 cm", "2sqrt(3)", "cm"))
        self.assertFalse(check_generated_answer("0.75", "3/4"))
        self.assertFalse(check_generated_answer("5", "6", "inches"))


class GeneratedProblemStorageTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)
        self.user_id = create_user(self.conn, "student@example.com", "hash")

    def test_store_check_and_scope_to_user(self):
        generated_id = create_generated_problem(self.conn, self.user_id, SOURCE, generated())
        other_id = create_user(self.conn, "other@example.com", "hash")

        record_generated_check(self.conn, self.user_id, generated_id, "6", True)
        row = get_generated_problem(self.conn, self.user_id, generated_id)

        self.assertEqual(row["subject"], "Geometry")
        self.assertEqual(row["is_correct"], 1)
        self.assertIsNone(get_generated_problem(self.conn, other_id, generated_id))
        self.assertEqual(len(get_generated_problems_for_user(self.conn, self.user_id)), 1)
        self.assertEqual(get_generated_problems_for_user(self.conn, other_id), [])

    def test_practice_views_escape_generated_text(self):
        bad = generated()
        bad["problem"] = "<script>alert(1)</script> What is x?"
        generated_id = create_generated_problem(self.conn, self.user_id, SOURCE, bad)
        row = get_generated_problem(self.conn, self.user_id, generated_id)
        user = {"email": "student@example.com"}

        page = render_practice_page(user, row, SOURCE)
        listing = render_generated_list_page(user, [row])

        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("Modeled on", page)
        self.assertIn("2025 Sprint #3", page)
        self.assertIn('action="/check-practice"', page)
        self.assertIn("Generate another like this", page)
        self.assertNotIn("<script>alert", listing)
        self.assertIn("Geometry · Easy", listing)


if __name__ == "__main__":
    unittest.main()


class BackgroundGenerationTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "app.sqlite3"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)
        self.user_id = create_user(self.conn, "student@example.com", "hash")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_job_completes_pending_problem(self):
        from mathcounts_platform.db import create_pending_generated_problem
        from mathcounts_platform.server import run_generation_job

        generated_id = create_pending_generated_problem(self.conn, self.user_id, SOURCE)
        self.assertEqual(get_generated_problem(self.conn, self.user_id, generated_id)["status"], "pending")

        run_generation_job(self.db_path, generated_id, SOURCE, FakeClient([generated(), {"answer": "6"}]))

        row = get_generated_problem(self.conn, self.user_id, generated_id)
        self.assertEqual(row["status"], "ready")
        self.assertEqual(row["answer"], "6")

    def test_job_records_failure_message(self):
        from mathcounts_platform.db import create_pending_generated_problem
        from mathcounts_platform.server import run_generation_job

        generated_id = create_pending_generated_problem(self.conn, self.user_id, SOURCE)

        run_generation_job(self.db_path, generated_id, SOURCE, FakeClient([GeneratorError("DeepSeek is down.")]))

        row = get_generated_problem(self.conn, self.user_id, generated_id)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error"], "DeepSeek is down.")

    def test_stale_pending_jobs_expire(self):
        from mathcounts_platform.db import create_pending_generated_problem, expire_stale_generations

        generated_id = create_pending_generated_problem(self.conn, self.user_id, SOURCE)
        self.conn.execute(
            "UPDATE generated_problems SET created_at = datetime('now', '-1 hour') WHERE id = ?", (generated_id,)
        )

        expire_stale_generations(self.conn)

        self.assertEqual(get_generated_problem(self.conn, self.user_id, generated_id)["status"], "failed")

    def test_pending_and_failed_pages(self):
        from mathcounts_platform.db import create_pending_generated_problem, fail_generated_problem

        user = {"email": "student@example.com"}
        pending_id = create_pending_generated_problem(self.conn, self.user_id, SOURCE)
        failed_id = create_pending_generated_problem(self.conn, self.user_id, SOURCE)
        fail_generated_problem(self.conn, failed_id, "Out of <tries>")

        pending_page = render_practice_page(user, get_generated_problem(self.conn, self.user_id, pending_id))
        failed_page = render_practice_page(user, get_generated_problem(self.conn, self.user_id, failed_id))
        listing = render_generated_list_page(user, get_generated_problems_for_user(self.conn, self.user_id))

        self.assertIn('http-equiv="refresh"', pending_page)
        self.assertIn("Generating your problem", pending_page)
        self.assertNotIn('action="/check-practice"', pending_page)
        self.assertIn("Out of &lt;tries&gt;", failed_page)
        self.assertIn("Try again", failed_page)
        self.assertIn("status-pending", listing)
        self.assertIn("status-failed", listing)


class GeneratedSchemaMigrationTest(unittest.TestCase):
    def test_migrate_adds_status_columns_to_existing_table(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE generated_problems (
              id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
              source_year INTEGER NOT NULL, source_round TEXT NOT NULL,
              source_question_number INTEGER NOT NULL, subject TEXT NOT NULL,
              difficulty TEXT NOT NULL, problem_text TEXT NOT NULL, answer TEXT NOT NULL,
              unit TEXT NOT NULL DEFAULT '', solution TEXT NOT NULL DEFAULT '',
              submitted_answer TEXT, is_correct INTEGER, checked_at TEXT,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO generated_problems (user_id, source_year, source_round, source_question_number, "
            "subject, difficulty, problem_text, answer) VALUES (1, 2025, 'Sprint', 1, 'Algebra', 'Easy', 'p', '1')"
        )

        migrate(conn)
        migrate(conn)

        columns = {row[1] for row in conn.execute("PRAGMA table_info(generated_problems)")}
        self.assertTrue({"status", "error"} <= columns)
        self.assertEqual(conn.execute("SELECT status FROM generated_problems").fetchone()[0], "ready")
