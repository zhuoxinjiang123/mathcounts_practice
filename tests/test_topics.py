import sqlite3
import unittest

from mathcounts_platform.db import create_problem_attempt, create_user, migrate, upsert_answer_key
from mathcounts_platform.grading import grade_answers
from mathcounts_platform.server import load_problem_statuses, save_graded_attempt
from mathcounts_platform.topics import (
    adjacent_problems,
    clean_filters,
    estimate_difficulty,
    filter_problems,
    group_problems,
    parse_problem_tags_csv,
    problem_page_url,
    status_for,
    subject_summary,
)
from mathcounts_platform.views import render_problem_page, render_results_page, render_topics_page


SAMPLE_CSV = """year,round,question_number,subject,difficulty,page,summary
2025,Sprint,1,Algebra,,11,Consecutive even integers
2025,Sprint,25,Geometry,,16,Circle inscribed in a square
2025,Target,3,Number Theory,,19,Remainders of powers
2024,Sprint,2,Algebra,Hard,11,Manually overridden difficulty
"""


class TopicsTest(unittest.TestCase):
    def setUp(self):
        self.problems = parse_problem_tags_csv(SAMPLE_CSV)

    def test_difficulty_is_estimated_from_round_position(self):
        self.assertEqual(estimate_difficulty("Sprint", 10), "Easy")
        self.assertEqual(estimate_difficulty("Sprint", 11), "Medium")
        self.assertEqual(estimate_difficulty("Sprint", 21), "Hard")
        self.assertEqual(estimate_difficulty("Target", 2), "Easy")
        self.assertEqual(estimate_difficulty("Target", 7), "Hard")
        self.assertEqual(estimate_difficulty("Team", 5), "Medium")

    def test_parse_uses_estimate_unless_csv_overrides(self):
        by_key = {(p["year"], p["round"], p["question_number"]): p for p in self.problems}

        self.assertEqual(by_key[(2025, "Sprint", 1)]["difficulty"], "Easy")
        self.assertEqual(by_key[(2025, "Sprint", 25)]["difficulty"], "Hard")
        self.assertEqual(by_key[(2024, "Sprint", 2)]["difficulty"], "Hard")
        self.assertEqual(by_key[(2025, "Target", 3)]["page"], 19)

    def test_parse_rejects_unknown_subject(self):
        with self.assertRaises(ValueError):
            parse_problem_tags_csv("year,round,question_number,subject\n2025,Sprint,1,Calculus\n")

    def test_problems_sorted_newest_year_then_round_order(self):
        keys = [(p["year"], p["round"], p["question_number"]) for p in self.problems]

        self.assertEqual(
            keys,
            [(2025, "Sprint", 1), (2025, "Sprint", 25), (2025, "Target", 3), (2024, "Sprint", 2)],
        )

    def test_group_by_subject_then_difficulty(self):
        grouped = group_problems(self.problems)

        self.assertEqual(list(grouped), ["Algebra", "Geometry", "Number Theory"])
        self.assertEqual(list(grouped["Algebra"]), ["Easy", "Hard"])
        self.assertEqual(len(grouped["Geometry"]["Hard"]), 1)

    def test_filter_by_subject_difficulty_round_and_status(self):
        statuses = {(2025, "Sprint", 1): True, (2025, "Sprint", 25): False}

        self.assertEqual(len(filter_problems(self.problems, {"subject": "Algebra"})), 2)
        self.assertEqual(len(filter_problems(self.problems, {"difficulty": "Hard"})), 2)
        self.assertEqual(len(filter_problems(self.problems, {"round": "Target"})), 1)
        missed = filter_problems(self.problems, {"status": "missed"}, statuses)
        self.assertEqual([p["question_number"] for p in missed], [25])
        self.assertEqual(len(filter_problems(self.problems, {"status": "new"}, statuses)), 2)

    def test_clean_filters_drops_unknown_values(self):
        self.assertEqual(
            clean_filters({"subject": "Geometry", "difficulty": "Impossible", "round": "<b>", "status": "solved"}),
            {"subject": "Geometry", "status": "solved"},
        )

    def test_adjacent_problems_work_when_current_is_filtered_out(self):
        current = self.problems[1]
        remaining = [self.problems[0], self.problems[2]]

        previous, following = adjacent_problems(remaining, current)

        self.assertEqual(previous, self.problems[0])
        self.assertEqual(following, self.problems[2])

    def test_problem_page_url_points_at_problem_page(self):
        self.assertEqual(problem_page_url("/past_paper/a.pdf#page=11", 14), "/past_paper/a.pdf#page=14")
        self.assertEqual(problem_page_url("/past_paper/a.pdf", 3), "/past_paper/a.pdf#page=3")
        self.assertEqual(problem_page_url("/past_paper/a.pdf#page=11", None), "/past_paper/a.pdf#page=11")

    def test_subject_summary_counts_tried_and_solved(self):
        statuses = {(2025, "Sprint", 1): True, (2024, "Sprint", 2): False}

        summary = {item["subject"]: item for item in subject_summary(self.problems, statuses)}

        self.assertEqual(summary["Algebra"]["total"], 2)
        self.assertEqual(summary["Algebra"]["tried"], 2)
        self.assertEqual(summary["Algebra"]["solved"], 1)
        self.assertEqual(summary["Algebra"]["by_difficulty"], {"Easy": 1, "Medium": 0, "Hard": 1})
        self.assertEqual(summary["Counting & Probability"]["total"], 0)


class ProblemStatusTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)
        self.user_id = create_user(self.conn, "student@example.com", "hash")
        upsert_answer_key(self.conn, 2025, "Target", 1, "7", 2)
        upsert_answer_key(self.conn, 2025, "Target", 2, "9 cm||9", 2)

    def test_round_attempts_and_single_checks_combine_latest_wins(self):
        keys = self.conn.execute("SELECT * FROM answer_keys").fetchall()
        submitted = {"1": "7", "2": "4"}
        save_graded_attempt(self.conn, self.user_id, 2025, "Target", submitted, grade_answers(keys, submitted))

        statuses = load_problem_statuses(self.conn, self.user_id)
        self.assertEqual(statuses, {(2025, "Target", 1): True, (2025, "Target", 2): False})

        create_problem_attempt(self.conn, self.user_id, 2025, "Target", 2, "9", True)

        statuses = load_problem_statuses(self.conn, self.user_id)
        self.assertTrue(statuses[(2025, "Target", 2)])
        self.assertEqual(status_for({"year": 2025, "round": "Target", "question_number": 2}, statuses), "solved")

    def test_statuses_are_regraded_against_current_answer_key(self):
        create_problem_attempt(self.conn, self.user_id, 2025, "Target", 1, "8", False)
        upsert_answer_key(self.conn, 2025, "Target", 1, "8", 2)

        self.assertTrue(load_problem_statuses(self.conn, self.user_id)[(2025, "Target", 1)])

    def test_other_users_checks_are_ignored(self):
        other_id = create_user(self.conn, "other@example.com", "hash")
        create_problem_attempt(self.conn, other_id, 2025, "Target", 1, "7", True)

        self.assertEqual(load_problem_statuses(self.conn, self.user_id), {})


class TopicViewTest(unittest.TestCase):
    def setUp(self):
        self.problems = parse_problem_tags_csv(SAMPLE_CSV)
        self.user = {"email": "student@example.com"}

    def test_topics_page_groups_and_marks_status(self):
        statuses = {(2025, "Sprint", 1): True}
        html = render_topics_page(
            user=self.user,
            problems=self.problems,
            grouped=group_problems(self.problems),
            summary=subject_summary(self.problems, statuses),
            filters={"subject": "Algebra"},
            statuses=statuses,
        )

        self.assertIn('href="/topics"', html)
        self.assertIn("Algebra", html)
        self.assertIn("Counting &amp; Probability", html)
        self.assertIn("2025 Sprint #1", html)
        self.assertIn("status-solved", html)
        self.assertIn('<option value="Algebra" selected>', html)
        self.assertIn("/problem?year=2025&amp;round=Sprint&amp;q=1&amp;subject=Algebra", html)

    def test_topics_page_empty_state(self):
        html = render_topics_page(self.user, [], {}, subject_summary(self.problems, {}), {"status": "missed"}, {})

        self.assertIn("No problems match these filters.", html)

    def test_problem_page_shows_check_result_and_answer(self):
        html = render_problem_page(
            user=self.user,
            problem=self.problems[1],
            paper_url="/past_paper/a.pdf#page=16",
            filters={"difficulty": "Hard"},
            status="missed",
            answer_key_available=True,
            check={"submitted_answer": "<script>", "is_correct": False},
            correct_answer="12 cm",
            previous_problem=self.problems[0],
            next_problem=None,
        )

        self.assertIn("2025 Sprint #25", html)
        self.assertIn("Geometry · Hard", html)
        self.assertIn('src="/past_paper/a.pdf#page=16&amp;zoom=page-width"', html)
        self.assertIn('action="/check-problem"', html)
        self.assertIn('name="difficulty" value="Hard"', html)
        self.assertIn("Not quite.", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("12 cm", html)
        self.assertIn("Previous", html)
        self.assertNotIn("Next &rarr;", html)

    def test_results_page_shows_topic_column_when_tagged(self):
        html = render_results_page(
            self.user,
            {"score": 1, "max_score": 1},
            [{"question_number": 1, "submitted_answer": "24", "correct_answer": "24", "points": 1, "is_correct": True}],
            {1: self.problems[0]},
        )

        self.assertIn("<th>Topic</th>", html)
        self.assertIn("Algebra · Easy", html)


if __name__ == "__main__":
    unittest.main()
