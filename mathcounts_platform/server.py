import argparse
import sqlite3
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from mathcounts_platform.auth import create_session, hash_password, verify_password
from mathcounts_platform.db import (
    create_attempt,
    create_user,
    get_answer_keys,
    get_attempt,
    get_attempt_answers,
    get_attempts_for_user,
    get_gradable_resource,
    get_reference_resources,
    get_user_by_email,
    get_user_for_session,
    get_years,
    migrate,
)
from mathcounts_platform.grading import grade_answers
from mathcounts_platform.rounds import is_answer_key_complete
from mathcounts_platform.views import (
    render_dashboard_page,
    render_history_page,
    render_login_page,
    render_register_page,
    render_results_page,
    render_test_page,
)


DEFAULT_DB_PATH = Path("data/app.sqlite3")
STATIC_DIR = Path("static")
SESSION_COOKIE = "mathcounts_session"


def connect(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    return conn


class MathcountsHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB_PATH

    def do_GET(self):
        parsed = urlparse(self.path)
        routes = {
            "/": self._get_home,
            "/login": self._get_login,
            "/register": self._get_register,
            "/dashboard": self._get_dashboard,
            "/results": self._get_results,
            "/test": self._get_test,
            "/history": self._get_history,
        }
        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path)
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
            "/logout": self._post_logout,
            "/submit-attempt": self._post_submit_attempt,
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
            self._send_html(render_results_page(user, attempt, get_attempt_answers(conn, attempt_id)))

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
        if not static_path.is_file():
            self._send_html("Not found", status=404)
            return
        content_type = "text/css" if static_path.suffix == ".css" else "application/javascript"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()
        self.wfile.write(static_path.read_bytes())

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    run(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
