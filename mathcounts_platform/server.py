import argparse
import json
import random
import sqlite3
import threading
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from mathcounts_platform.auth import create_password_reset_token, create_session, hash_password, verify_password
from mathcounts_platform.db import (
    complete_generated_problem,
    create_attempt,
    create_pending_generated_problem,
    create_problem_attempt,
    create_user,
    expire_stale_generations,
    fail_generated_problem,
    get_all_answer_keys,
    get_answer_keys,
    get_attempt,
    get_attempt_answers,
    get_attempts_for_user,
    get_generated_problem,
    get_generated_problems_for_user,
    get_gradable_resource,
    get_problem_attempt,
    get_problem_attempts_for_user,
    get_reference_resources,
    get_user_by_email,
    get_user_for_password_reset_token,
    get_user_for_session,
    get_years,
    mark_password_reset_token_used,
    migrate,
    record_generated_check,
    update_user_password,
)
from mathcounts_platform.generator import (
    DeepSeekClient,
    GeneratorError,
    check_generated_answer,
    generate_similar_problem,
    load_dotenv,
)
from mathcounts_platform.grading import answer_matches, display_answer, grade_answers
from mathcounts_platform.rounds import is_answer_key_complete
from mathcounts_platform.topics import (
    DEFAULT_TAGS_PATH,
    adjacent_problems,
    clean_filters,
    filter_problems,
    find_problem,
    group_problems,
    load_problem_tags,
    problem_page_url,
    status_for,
    subject_summary,
)
from mathcounts_platform.views import (
    render_dashboard_page,
    render_forgot_password_page,
    render_generated_list_page,
    render_generation_error_page,
    render_practice_page,
    render_history_page,
    render_login_page,
    render_problem_page,
    render_register_page,
    render_reset_password_page,
    render_results_page,
    render_test_page,
    render_topics_page,
)


DEFAULT_DB_PATH = Path("data/app.sqlite3")
STATIC_DIR = Path("static")
PAST_PAPER_DIR = Path("past_paper")
SESSION_COOKIE = "mathcounts_session"


def connect(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


class MathcountsHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB_PATH
    tags_path = DEFAULT_TAGS_PATH
    generator_client_factory = staticmethod(DeepSeekClient.from_environ)

    def do_GET(self):
        parsed = urlparse(self.path)
        routes = {
            "/": self._get_home,
            "/login": self._get_login,
            "/register": self._get_register,
            "/forgot-password": self._get_forgot_password,
            "/reset-password": self._get_reset_password,
            "/dashboard": self._get_dashboard,
            "/results": self._get_results,
            "/test": self._get_test,
            "/history": self._get_history,
            "/topics": self._get_topics,
            "/problem": self._get_problem,
            "/practice": self._get_practice,
        }
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path)
            return
        if parsed.path.startswith("/past_paper/"):
            self._serve_past_paper(parsed.path)
            return
        handler = routes.get(parsed.path)
        if handler is None:
            self._send_html("Not found", status=404)
            return
        handler(parsed)

    def do_POST(self):
        parsed = urlparse(self.path)
        routes = {
            "/login": self._post_login,
            "/register": self._post_register,
            "/forgot-password": self._post_forgot_password,
            "/reset-password": self._post_reset_password,
            "/logout": self._post_logout,
            "/submit-attempt": self._post_submit_attempt,
            "/check-problem": self._post_check_problem,
            "/generate-problem": self._post_generate_problem,
            "/check-practice": self._post_check_practice,
        }
        handler = routes.get(parsed.path)
        if handler is None:
            self._send_html("Not found", status=404)
            return
        handler(parsed)

    def _get_home(self, parsed):
        if self._current_user():
            self._redirect("/dashboard")
        else:
            self._redirect("/login")

    def _get_login(self, parsed):
        self._send_html(render_login_page())

    def _get_register(self, parsed):
        self._send_html(render_register_page())

    def _get_forgot_password(self, parsed):
        self._send_html(render_forgot_password_page())

    def _get_reset_password(self, parsed):
        query = parse_qs(parsed.query)
        token = query.get("token", [""])[0]
        with connect(self.db_path) as conn:
            if not token or get_user_for_password_reset_token(conn, token) is None:
                self._send_html(
                    render_reset_password_page(error="This reset link is invalid or expired."),
                    status=400,
                )
                return
        self._send_html(render_reset_password_page(token))

    def _get_dashboard(self, parsed):
        user = self._require_user()
        if not user:
            return
        with connect(self.db_path) as conn:
            self._send_html(
                render_dashboard_page(
                    user=user,
                    years=get_years(conn),
                    attempts=get_attempts_for_user(conn, user["id"]),
                )
            )

    def _get_test(self, parsed):
        user = self._require_user()
        if not user:
            return
        query = parse_qs(parsed.query)
        try:
            year = int(query.get("year", [""])[0])
        except ValueError:
            self._send_html("Invalid year", status=400)
            return
        round_name = query.get("round", [""])[0]
        with connect(self.db_path) as conn:
            resource = get_gradable_resource(conn, year, round_name)
            if resource is None:
                self._send_html("Round not found", status=404)
                return
            self._send_html(
                render_test_page(
                    user=user,
                    year=year,
                    round_name=round_name,
                    resource=resource,
                    answer_keys=get_answer_keys(conn, year, round_name),
                    reference_links=get_reference_resources(conn, year),
                )
            )

    def _get_history(self, parsed):
        user = self._require_user()
        if not user:
            return
        with connect(self.db_path) as conn:
            self._send_html(render_history_page(user, get_attempts_for_user(conn, user["id"])))

    def _get_results(self, parsed):
        user = self._require_user()
        if not user:
            return
        query = parse_qs(parsed.query)
        try:
            attempt_id = int(query.get("id", [""])[0])
        except ValueError:
            self._send_html("Invalid attempt", status=400)
            return
        with connect(self.db_path) as conn:
            attempt = get_attempt(conn, user["id"], attempt_id)
            if attempt is None:
                self._send_html("Attempt not found", status=404)
                return
            attempt, results = load_attempt_results(conn, user["id"], attempt_id)
            problem_tags = {
                problem["question_number"]: problem
                for problem in load_problem_tags(self.tags_path)
                if problem["year"] == int(attempt["year"]) and problem["round"] == attempt["round"]
            }
            self._send_html(render_results_page(user, attempt, results, problem_tags))

    def _get_topics(self, parsed):
        user = self._require_user()
        if not user:
            return
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        filters = clean_filters(query)
        problems = load_problem_tags(self.tags_path)
        with connect(self.db_path) as conn:
            statuses = load_problem_statuses(conn, user["id"])
        selected = filter_problems(problems, filters, statuses)
        self._send_html(
            render_topics_page(
                user=user,
                problems=selected,
                grouped=group_problems(selected),
                summary=subject_summary(problems, statuses),
                filters=filters,
                statuses=statuses,
            )
        )

    def _get_problem(self, parsed):
        user = self._require_user()
        if not user:
            return
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        try:
            year = int(query.get("year", ""))
            question_number = int(query.get("q", ""))
        except ValueError:
            self._send_html("Invalid problem", status=400)
            return
        round_name = query.get("round", "")
        filters = clean_filters(query)
        problems = load_problem_tags(self.tags_path)
        problem = find_problem(problems, year, round_name, question_number)
        if problem is None:
            self._send_html("Problem not found", status=404)
            return

        with connect(self.db_path) as conn:
            resource = get_gradable_resource(conn, year, round_name)
            if resource is None:
                self._send_html("Round not found", status=404)
                return
            key = _answer_key_for(get_answer_keys(conn, year, round_name), question_number)
            check = None
            if query.get("check"):
                try:
                    check = get_problem_attempt(conn, user["id"], int(query["check"]))
                except ValueError:
                    check = None
                if check is not None and (check["year"], check["round"], check["question_number"]) != (
                    year,
                    round_name,
                    question_number,
                ):
                    check = None
            if check is not None and key is not None:
                # Re-grade so a corrected answer key is reflected, like round results.
                check = dict(check)
                check["is_correct"] = answer_matches(check["submitted_answer"], key["answer"])
            statuses = load_problem_statuses(conn, user["id"])

        previous_problem, next_problem = adjacent_problems(filter_problems(problems, filters, statuses), problem)
        self._send_html(
            render_problem_page(
                user=user,
                problem=problem,
                paper_url=problem_page_url(resource["url"], problem["page"]),
                filters=filters,
                status=status_for(problem, statuses),
                answer_key_available=key is not None,
                check=check,
                correct_answer=display_answer(key["answer"]) if key is not None else None,
                previous_problem=previous_problem,
                next_problem=next_problem,
            )
        )

    def _post_register(self, parsed):
        form = self._read_form()
        email = form.get("email", "").strip().casefold()
        password = form.get("password", "")
        if not email or len(password) < 8:
            self._send_html(render_register_page("Use an email and a password with at least 8 characters."), status=400)
            return
        with connect(self.db_path) as conn:
            if get_user_by_email(conn, email):
                self._send_html(render_register_page("An account with that email already exists."), status=400)
                return
            user_id = create_user(conn, email, hash_password(password))
            token = create_session(conn, user_id)
        self._redirect("/dashboard", cookie=self._session_cookie(token))

    def _post_login(self, parsed):
        form = self._read_form()
        email = form.get("email", "").strip().casefold()
        password = form.get("password", "")
        with connect(self.db_path) as conn:
            user = get_user_by_email(conn, email)
            if not user or not verify_password(password, user["password_hash"]):
                self._send_html(render_login_page("Invalid email or password."), status=400)
                return
            token = create_session(conn, user["id"])
        self._redirect("/dashboard", cookie=self._session_cookie(token))

    def _post_forgot_password(self, parsed):
        form = self._read_form()
        email = form.get("email", "").strip().casefold()
        reset_link = None
        with connect(self.db_path) as conn:
            user = get_user_by_email(conn, email)
            if user:
                token = create_password_reset_token(conn, user["id"])
                reset_link = f"/reset-password?token={token}"
        self._send_html(
            render_forgot_password_page(
                message="If that account exists, a reset link has been created.",
                reset_link=reset_link,
            )
        )

    def _post_reset_password(self, parsed):
        form = self._read_form()
        token = form.get("token", "")
        password = form.get("password", "")
        if len(password) < 8:
            self._send_html(
                render_reset_password_page(token, "Use a password with at least 8 characters."),
                status=400,
            )
            return
        with connect(self.db_path) as conn:
            user = get_user_for_password_reset_token(conn, token)
            if user is None:
                self._send_html(
                    render_reset_password_page(error="This reset link is invalid or expired."),
                    status=400,
                )
                return
            update_user_password(conn, user["id"], hash_password(password))
            mark_password_reset_token_used(conn, token)
        self._send_html(render_login_page(message="Password reset successful. Log in with your new password."))

    def _post_logout(self, parsed):
        self._redirect("/login", cookie=f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")

    def _post_submit_attempt(self, parsed):
        user = self._require_user()
        if not user:
            return
        form = self._read_form()
        try:
            year = int(form.get("year", ""))
        except ValueError:
            self._send_html("Invalid year", status=400)
            return
        round_name = form.get("round", "")

        with connect(self.db_path) as conn:
            answer_keys = get_answer_keys(conn, year, round_name)
            if not is_answer_key_complete(round_name, answer_keys):
                self._send_html("This round does not have an imported answer key yet.", status=400)
                return
            submitted_answers = {
                str(key["question_number"]): form.get(f"answer_{int(key['question_number'])}", "")
                for key in answer_keys
            }
            grade = grade_answers(answer_keys, submitted_answers)
            attempt_id = save_graded_attempt(conn, user["id"], year, round_name, submitted_answers, grade)
        self._redirect(f"/results?id={attempt_id}")

    def _post_check_problem(self, parsed):
        user = self._require_user()
        if not user:
            return
        form = self._read_form()
        try:
            year = int(form.get("year", ""))
            question_number = int(form.get("q", ""))
        except ValueError:
            self._send_html("Invalid problem", status=400)
            return
        round_name = form.get("round", "")
        if find_problem(load_problem_tags(self.tags_path), year, round_name, question_number) is None:
            self._send_html("Problem not found", status=404)
            return
        submitted_answer = form.get("answer", "").strip()
        with connect(self.db_path) as conn:
            key = _answer_key_for(get_answer_keys(conn, year, round_name), question_number)
            if key is None:
                self._send_html("This problem does not have an imported answer key yet.", status=400)
                return
            check_id = create_problem_attempt(
                conn,
                user["id"],
                year,
                round_name,
                question_number,
                submitted_answer,
                answer_matches(submitted_answer, key["answer"]),
            )
        params = {"year": year, "round": round_name, "q": question_number, "check": check_id}
        params.update(clean_filters(form))
        self._redirect(f"/problem?{urlencode(params)}")

    def _get_practice(self, parsed):
        user = self._require_user()
        if not user:
            return
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        with connect(self.db_path) as conn:
            expire_stale_generations(conn)
            if not query.get("id"):
                self._send_html(render_generated_list_page(user, get_generated_problems_for_user(conn, user["id"])))
                return
            try:
                generated = get_generated_problem(conn, user["id"], int(query["id"]))
            except ValueError:
                generated = None
        if generated is None:
            self._send_html("Practice problem not found", status=404)
            return
        source = find_problem(
            load_problem_tags(self.tags_path),
            generated["source_year"],
            generated["source_round"],
            generated["source_question_number"],
        )
        self._send_html(render_practice_page(user, generated, source))

    def _post_generate_problem(self, parsed):
        user = self._require_user()
        if not user:
            return
        form = self._read_form()
        problems = load_problem_tags(self.tags_path)
        source = None
        if form.get("q"):
            try:
                source = find_problem(problems, int(form.get("year", "")), form.get("round", ""), int(form["q"]))
            except ValueError:
                source = None
        else:
            filters = clean_filters(form)
            filters.pop("status", None)
            candidates = filter_problems(problems, filters)
            source = random.choice(candidates) if candidates else None
        if source is None:
            self._send_html("Problem not found", status=404)
            return

        try:
            client = self.generator_client_factory()
        except GeneratorError as error:
            back_href = "/topics"
            if form.get("q"):
                back_href = "/problem?" + urlencode(
                    {"year": source["year"], "round": source["round"], "q": source["question_number"]}
                )
            self._send_html(render_generation_error_page(user, str(error), back_href), status=503)
            return

        with connect(self.db_path) as conn:
            generated_id = create_pending_generated_problem(conn, user["id"], source)
        self.start_generation_job(self.db_path, generated_id, source, client)
        self._redirect(f"/practice?id={generated_id}")

    @staticmethod
    def start_generation_job(db_path, generated_id, source, client):
        threading.Thread(
            target=run_generation_job,
            args=(db_path, generated_id, source, client),
            name=f"generate-{generated_id}",
            daemon=True,
        ).start()

    def _post_check_practice(self, parsed):
        user = self._require_user()
        if not user:
            return
        form = self._read_form()
        try:
            generated_id = int(form.get("id", ""))
        except ValueError:
            self._send_html("Invalid practice problem", status=400)
            return
        submitted_answer = form.get("answer", "").strip()
        with connect(self.db_path) as conn:
            generated = get_generated_problem(conn, user["id"], generated_id)
            if generated is None:
                self._send_html("Practice problem not found", status=404)
                return
            if generated["status"] != "ready":
                self._send_html("This practice problem isn't ready yet.", status=409)
                return
            is_correct = check_generated_answer(submitted_answer, generated["answer"], generated["unit"])
            record_generated_check(conn, user["id"], generated_id, submitted_answer, is_correct)
        self._redirect(f"/practice?id={generated_id}")

    def _require_user(self):
        user = self._current_user()
        if not user:
            self._redirect("/login")
        return user

    def _current_user(self):
        cookie_header = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie()
        jar.load(cookie_header)
        morsel = jar.get(SESSION_COOKIE)
        if not morsel:
            return None
        with connect(self.db_path) as conn:
            return get_user_for_session(conn, morsel.value)

    def _read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        return {key: values[0] for key, values in parse_qs(raw_body, keep_blank_values=True).items()}

    def _serve_static(self, path):
        relative = path.removeprefix("/static/")
        static_path = STATIC_DIR / relative
        self._serve_file(static_path)

    def _serve_past_paper(self, path):
        relative = unquote(path.removeprefix("/past_paper/"))
        paper_path = safe_child_path(PAST_PAPER_DIR, relative)
        if paper_path is None:
            self._send_html("Not found", status=404)
            return
        self._serve_file(paper_path)

    def _serve_file(self, file_path):
        if not file_path.is_file():
            self._send_html("Not found", status=404)
            return
        content_type = content_type_for_path(file_path)
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        self.wfile.write(file_path.read_bytes())

    def _send_html(self, html, status=200):
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location, cookie=None):
        self.send_response(303)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _session_cookie(self, token):
        return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax"


def run(host="127.0.0.1", port=8000, db_path=DEFAULT_DB_PATH):
    load_dotenv()
    MathcountsHandler.db_path = Path(db_path)
    MathcountsHandler.db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(MathcountsHandler.db_path):
        pass
    server = ThreadingHTTPServer((host, int(port)), MathcountsHandler)
    print(f"Serving MATHCOUNTS National Practice at http://{host}:{port}")
    server.serve_forever()


def save_graded_attempt(conn, user_id, year, round_name, submitted_answers, grade):
    return create_attempt(
        conn,
        user_id,
        year,
        round_name,
        submitted_answers,
        grade["results"],
        grade["score"],
        grade["max_score"],
    )


def load_attempt_results(conn, user_id, attempt_id):
    attempt = get_attempt(conn, user_id, attempt_id)
    if attempt is None:
        return None, []

    answer_keys = get_answer_keys(conn, attempt["year"], attempt["round"])
    if is_answer_key_complete(attempt["round"], answer_keys):
        submitted_answers = json.loads(attempt["submitted_answers_json"])
        grade = grade_answers(answer_keys, submitted_answers)
        current_attempt = dict(attempt)
        current_attempt["score"] = grade["score"]
        current_attempt["max_score"] = grade["max_score"]
        return current_attempt, grade["results"]

    return attempt, get_attempt_answers(conn, attempt_id)


def run_generation_job(db_path, generated_id, source, client):
    """Generate a problem in the background and record the outcome on its row."""
    try:
        result = generate_similar_problem(source, client)
    except GeneratorError as error:
        message = str(error)
    except Exception:  # noqa: BLE001 - any failure must end the pending state
        message = "Something went wrong while generating. Please try again."
    else:
        with connect(db_path) as conn:
            complete_generated_problem(conn, generated_id, result)
        return
    with connect(db_path) as conn:
        fail_generated_problem(conn, generated_id, message)


def load_problem_statuses(conn, user_id):
    """Map (year, round, question_number) -> bool for the user's latest answer.

    Combines full-round attempts and single-problem checks, re-grading each
    against the current answer key. A blank answer in a submitted round counts
    as missed.
    """
    answer_keys = {
        (int(key["year"]), key["round"], int(key["question_number"])): key["answer"]
        for key in get_all_answer_keys(conn)
    }
    events = []
    for attempt in get_attempts_for_user(conn, user_id):
        submitted = json.loads(attempt["submitted_answers_json"])
        for question_number, answer in submitted.items():
            events.append(
                (
                    (attempt["submitted_at"], 0, attempt["id"]),
                    (int(attempt["year"]), attempt["round"], int(question_number)),
                    answer,
                )
            )
    for check in get_problem_attempts_for_user(conn, user_id):
        events.append(
            (
                (check["submitted_at"], 1, check["id"]),
                (int(check["year"]), check["round"], int(check["question_number"])),
                check["submitted_answer"],
            )
        )

    statuses = {}
    for _, key, answer in sorted(events, key=lambda event: event[0]):
        if key in answer_keys:
            statuses[key] = answer_matches(answer, answer_keys[key])
    return statuses


def _answer_key_for(answer_keys, question_number):
    return next((key for key in answer_keys if int(key["question_number"]) == int(question_number)), None)


def content_type_for_path(path):
    suffix = Path(path).suffix.lower()
    return {
        ".css": "text/css",
        ".js": "application/javascript",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")


def safe_child_path(root, relative_path):
    root_path = Path(root).resolve()
    child_path = (root_path / relative_path).resolve()
    if child_path == root_path or root_path not in child_path.parents:
        return None
    return child_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    run(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
