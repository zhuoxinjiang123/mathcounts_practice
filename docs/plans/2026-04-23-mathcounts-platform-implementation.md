# MATHCOUNTS Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a backend/database web platform where users log in, select MATHCOUNTS National tests by year, answer questions inside the app, receive automatic grading, and keep score history across devices.

**Architecture:** Use a dependency-light Python web app backed by SQLite. The app serves HTML/CSS/vanilla JavaScript, stores users/catalog/answer keys/attempts in SQLite, embeds or links the original source papers, and grades submitted answers against structured answer keys.

**Tech Stack:** Python 3 standard library, `http.server`, `sqlite3`, `unittest`, HTML, CSS, vanilla JavaScript.

---

## Implementation Notes

- This workspace is not currently a git repository. Execute commit steps only if a git repo is initialized before implementation.
- The source page lists National resources from 2000 through 2017.
- The local environment does not currently include `pdftotext`, `pypdf`, `PyPDF2`, or `pdfplumber`, so the MVP should support structured answer-key import instead of depending on PDF extraction.
- The app should still list every National paper immediately. Auto-graded submission should be enabled only when answer-key rows exist for the chosen year and round.
- Round scoring should be data-driven. Seed defaults are Sprint: 30 questions at 1 point each, Target: 8 questions at 2 points each, Team: 10 questions at 2 points each.

## Task 1: Project Scaffold And Smoke Test

**Files:**
- Create: `mathcounts_platform/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `README.md`
- Create: `.gitignore`

**Step 1: Write the failing test**

```python
# tests/test_smoke.py
import unittest

from mathcounts_platform import APP_NAME


class SmokeTest(unittest.TestCase):
    def test_app_name_exists(self):
        self.assertEqual(APP_NAME, "MATHCOUNTS National Practice")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_smoke -v`

Expected: FAIL with an import error or missing `APP_NAME`.

**Step 3: Write minimal implementation**

```python
# mathcounts_platform/__init__.py
APP_NAME = "MATHCOUNTS National Practice"
```

Add a short `README.md` with setup/run/test commands and a `.gitignore` for Python caches, SQLite files, and local env files.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_smoke -v`

Expected: PASS.

**Step 5: Commit**

If this is a git repo:

```bash
git add .gitignore README.md mathcounts_platform/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold mathcounts platform"
```

## Task 2: Grading Service

**Files:**
- Create: `mathcounts_platform/grading.py`
- Create: `tests/test_grading.py`

**Step 1: Write failing tests**

```python
# tests/test_grading.py
import unittest

from mathcounts_platform.grading import grade_answers, normalize_answer


class GradingTest(unittest.TestCase):
    def test_normalize_answer(self):
        self.assertEqual(normalize_answer("  ABC  "), "abc")

    def test_grade_answers_with_points(self):
        keys = [
            {"question_number": 1, "answer": "12", "points": 1},
            {"question_number": 2, "answer": "B", "points": 2},
            {"question_number": 3, "answer": "3/4", "points": 2},
        ]
        submitted = {"1": "12", "2": " b ", "3": "0.75"}

        result = grade_answers(keys, submitted)

        self.assertEqual(result["score"], 3)
        self.assertEqual(result["max_score"], 5)
        self.assertTrue(result["results"][0]["is_correct"])
        self.assertTrue(result["results"][1]["is_correct"])
        self.assertFalse(result["results"][2]["is_correct"])
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_grading -v`

Expected: FAIL because `mathcounts_platform.grading` does not exist.

**Step 3: Write minimal implementation**

```python
# mathcounts_platform/grading.py
def normalize_answer(value):
    return str(value or "").strip().casefold()


def grade_answers(answer_keys, submitted_answers):
    results = []
    score = 0
    max_score = 0

    for key in sorted(answer_keys, key=lambda row: int(row["question_number"])):
        question_number = int(key["question_number"])
        points = int(key.get("points", 1))
        correct_answer = key["answer"]
        submitted_answer = submitted_answers.get(str(question_number), "")
        is_correct = normalize_answer(submitted_answer) == normalize_answer(correct_answer)

        max_score += points
        if is_correct:
            score += points

        results.append({
            "question_number": question_number,
            "submitted_answer": submitted_answer,
            "correct_answer": correct_answer,
            "points": points,
            "is_correct": is_correct,
        })

    return {"score": score, "max_score": max_score, "results": results}
```

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_grading -v`

Expected: PASS.

**Step 5: Commit**

If this is a git repo:

```bash
git add mathcounts_platform/grading.py tests/test_grading.py
git commit -m "feat: add answer grading service"
```

## Task 3: SQLite Schema And Data Access

**Files:**
- Create: `mathcounts_platform/db.py`
- Create: `tests/test_db.py`

**Step 1: Write failing tests**

Test that migration creates tables and that a user, resource, answer key, and attempt can be inserted and fetched.

```python
# tests/test_db.py
import sqlite3
import unittest

from mathcounts_platform.db import (
    create_attempt,
    create_user,
    get_answer_keys,
    get_attempts_for_user,
    get_user_by_email,
    migrate,
    upsert_answer_key,
    upsert_resource,
)


class DatabaseTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_user_resource_key_and_attempt_roundtrip(self):
        user_id = create_user(self.conn, "student@example.com", "hash")
        upsert_resource(self.conn, 2017, "Sprint", "paper", "https://example.com/sprint", True)
        upsert_answer_key(self.conn, 2017, "Sprint", 1, "42", 1)

        keys = get_answer_keys(self.conn, 2017, "Sprint")
        attempt_id = create_attempt(
            self.conn,
            user_id,
            2017,
            "Sprint",
            {"1": "42"},
            [{"question_number": 1, "submitted_answer": "42", "correct_answer": "42", "points": 1, "is_correct": True}],
            1,
            1,
        )

        self.assertEqual(get_user_by_email(self.conn, "student@example.com")["id"], user_id)
        self.assertEqual(keys[0]["answer"], "42")
        self.assertEqual(get_attempts_for_user(self.conn, user_id)[0]["id"], attempt_id)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_db -v`

Expected: FAIL because `db.py` does not exist.

**Step 3: Implement schema**

Create these tables in `migrate(conn)`:

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  year INTEGER NOT NULL,
  label TEXT NOT NULL,
  kind TEXT NOT NULL,
  url TEXT NOT NULL,
  gradable INTEGER NOT NULL DEFAULT 0,
  UNIQUE(year, label, kind)
);

CREATE TABLE IF NOT EXISTS answer_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  year INTEGER NOT NULL,
  round TEXT NOT NULL,
  question_number INTEGER NOT NULL,
  answer TEXT NOT NULL,
  points INTEGER NOT NULL DEFAULT 1,
  UNIQUE(year, round, question_number)
);

CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  year INTEGER NOT NULL,
  round TEXT NOT NULL,
  submitted_answers_json TEXT NOT NULL,
  score INTEGER NOT NULL,
  max_score INTEGER NOT NULL,
  submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attempt_answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id INTEGER NOT NULL REFERENCES attempts(id),
  question_number INTEGER NOT NULL,
  submitted_answer TEXT NOT NULL,
  correct_answer TEXT NOT NULL,
  points INTEGER NOT NULL,
  is_correct INTEGER NOT NULL
);
```

Implement helper functions used by the test. Return `sqlite3.Row` objects or dictionaries consistently.

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_db -v`

Expected: PASS.

**Step 5: Commit**

If this is a git repo:

```bash
git add mathcounts_platform/db.py tests/test_db.py
git commit -m "feat: add sqlite persistence"
```

## Task 4: Authentication And Sessions

**Files:**
- Create: `mathcounts_platform/auth.py`
- Create: `tests/test_auth.py`
- Modify: `mathcounts_platform/db.py`

**Step 1: Write failing tests**

```python
# tests/test_auth.py
import sqlite3
import unittest

from mathcounts_platform.auth import hash_password, verify_password, create_session, hash_token
from mathcounts_platform.db import create_user, get_user_for_session, migrate


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_password_hash_roundtrip(self):
        hashed = hash_password("secret-pass")
        self.assertTrue(verify_password("secret-pass", hashed))
        self.assertFalse(verify_password("wrong-pass", hashed))

    def test_session_roundtrip(self):
        user_id = create_user(self.conn, "student@example.com", hash_password("secret-pass"))
        token = create_session(self.conn, user_id)
        self.assertNotEqual(token, hash_token(token))
        self.assertEqual(get_user_for_session(self.conn, token)["id"], user_id)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_auth -v`

Expected: FAIL because auth helpers do not exist.

**Step 3: Implement auth helpers**

Use only standard library modules:

- `hashlib.pbkdf2_hmac` for passwords.
- `secrets.token_urlsafe` for salts and session tokens.
- `hmac.compare_digest` for safe comparisons.
- `datetime` for session expiration.

Store password hashes as `pbkdf2_sha256$iterations$salt_hex$hash_hex`.

Store only `hash_token(raw_token)` in the `sessions` table.

**Step 4: Run tests**

Run: `python3 -m unittest tests.test_auth tests.test_db -v`

Expected: PASS.

**Step 5: Commit**

If this is a git repo:

```bash
git add mathcounts_platform/auth.py mathcounts_platform/db.py tests/test_auth.py
git commit -m "feat: add account authentication"
```

## Task 5: Catalog Parser And Seed Data

**Files:**
- Create: `mathcounts_platform/catalog.py`
- Create: `scripts/build_catalog.py`
- Create: `data/catalog.json`
- Create: `tests/fixtures/mathcounts_sample.html`
- Create: `tests/test_catalog.py`

**Step 1: Write failing parser test**

Use a small HTML fixture containing one year and one National row.

```python
# tests/test_catalog.py
import unittest

from mathcounts_platform.catalog import parse_national_resources


class CatalogTest(unittest.TestCase):
    def test_parse_national_resources(self):
        html = """
        <div class="paragraph"><strong><font size="6">2017</font></strong><br />
        <strong>NATIONAL: &nbsp;&nbsp;</strong>
        <a href="https://example.com/sprint" target="_blank">Sprint</a>&nbsp;|&nbsp;
        <a href="https://example.com/answers" target="_blank">Answers</a>
        </div>
        """

        catalog = parse_national_resources(html)

        self.assertEqual(catalog[0]["year"], 2017)
        self.assertEqual(catalog[0]["resources"][0]["label"], "Sprint")
        self.assertTrue(catalog[0]["resources"][0]["gradable"])
        self.assertFalse(catalog[0]["resources"][1]["gradable"])
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_catalog -v`

Expected: FAIL because catalog parser does not exist.

**Step 3: Implement parser**

Implement `parse_national_resources(html_text)` using regex or `html.parser` from the standard library. It should:

- Detect years from `<font size="6">YYYY</font>`.
- Extract the `NATIONAL` section only.
- Extract links and labels.
- Mark `Sprint`, `Target`, and `Team` as `gradable=True`.
- Mark all other resources as `gradable=False`.

**Step 4: Generate full catalog**

Run:

```bash
curl -L -o /tmp/mathcounts-source.html https://mathteamnyc.weebly.com/mathcounts.html
python3 scripts/build_catalog.py /tmp/mathcounts-source.html data/catalog.json
```

Expected: `data/catalog.json` contains 18 years, 2000 through 2017.

**Step 5: Add catalog database seeding**

Add `seed_catalog(conn, catalog_items)` to `mathcounts_platform/catalog.py`. It should call `upsert_resource` for each resource.

**Step 6: Run tests**

Run: `python3 -m unittest tests.test_catalog tests.test_db -v`

Expected: PASS.

**Step 7: Commit**

If this is a git repo:

```bash
git add data/catalog.json mathcounts_platform/catalog.py scripts/build_catalog.py tests/fixtures/mathcounts_sample.html tests/test_catalog.py
git commit -m "feat: seed mathcounts national catalog"
```

## Task 6: Answer Key Import

**Files:**
- Create: `mathcounts_platform/answer_keys.py`
- Create: `scripts/import_answer_keys.py`
- Create: `data/answer_keys.sample.csv`
- Create: `tests/test_answer_keys.py`

**Step 1: Write failing tests**

```python
# tests/test_answer_keys.py
import sqlite3
import unittest

from mathcounts_platform.answer_keys import parse_answer_key_csv, import_answer_keys
from mathcounts_platform.db import get_answer_keys, migrate


class AnswerKeyImportTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_parse_and_import_answer_keys(self):
        csv_text = "year,round,question_number,answer,points\\n2017,Sprint,1,42,1\\n2017,Target,1,B,2\\n"
        rows = parse_answer_key_csv(csv_text)
        import_answer_keys(self.conn, rows)

        sprint_keys = get_answer_keys(self.conn, 2017, "Sprint")
        self.assertEqual(sprint_keys[0]["answer"], "42")
        self.assertEqual(sprint_keys[0]["points"], 1)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_answer_keys -v`

Expected: FAIL because answer-key importer does not exist.

**Step 3: Implement importer**

Use the standard `csv` module. Required columns:

- `year`
- `round`
- `question_number`
- `answer`
- `points`

Validate that:

- `round` is one of `Sprint`, `Target`, or `Team`.
- `year` is between 2000 and 2017 for this source catalog.
- `question_number` and `points` are positive integers.

**Step 4: Add sample CSV**

Create `data/answer_keys.sample.csv`:

```csv
year,round,question_number,answer,points
2017,Sprint,1,example,1
2017,Target,1,example,2
2017,Team,1,example,2
```

**Step 5: Run tests**

Run: `python3 -m unittest tests.test_answer_keys -v`

Expected: PASS.

**Step 6: Commit**

If this is a git repo:

```bash
git add data/answer_keys.sample.csv mathcounts_platform/answer_keys.py scripts/import_answer_keys.py tests/test_answer_keys.py
git commit -m "feat: add answer key import"
```

## Task 7: Web Server Routes

**Files:**
- Create: `mathcounts_platform/server.py`
- Create: `mathcounts_platform/views.py`
- Create: `tests/test_views.py`
- Modify: `README.md`

**Step 1: Write failing view tests**

```python
# tests/test_views.py
import unittest

from mathcounts_platform.views import render_login_page, render_dashboard_page


class ViewTest(unittest.TestCase):
    def test_login_page_contains_form(self):
        html = render_login_page(error=None)
        self.assertIn("<form", html)
        self.assertIn("name=\"email\"", html)
        self.assertIn("name=\"password\"", html)

    def test_dashboard_lists_years(self):
        html = render_dashboard_page(
            user={"email": "student@example.com"},
            years=[{"year": 2017}, {"year": 2016}],
            attempts=[],
        )
        self.assertIn("2017", html)
        self.assertIn("2016", html)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_views -v`

Expected: FAIL because views do not exist.

**Step 3: Implement views**

Create simple HTML rendering functions in `views.py`:

- `render_base(title, body, user=None)`
- `render_login_page(error=None)`
- `render_register_page(error=None)`
- `render_dashboard_page(user, years, attempts)`
- `render_test_page(user, year, round_name, resource, answer_keys, reference_links)`
- `render_results_page(user, attempt, per_question_results)`
- `render_history_page(user, attempts)`

**Step 4: Implement route skeleton**

In `server.py`, implement a `BaseHTTPRequestHandler` subclass with routes:

- `GET /`
- `GET /login`
- `POST /login`
- `GET /register`
- `POST /register`
- `POST /logout`
- `GET /dashboard`
- `GET /test?year=2017&round=Sprint`
- `POST /submit-attempt`
- `GET /history`
- `GET /static/styles.css`
- `GET /static/app.js`

Use cookies for session token storage. Redirect unauthenticated users to `/login`.

**Step 5: Run tests**

Run: `python3 -m unittest tests.test_views -v`

Expected: PASS.

**Step 6: Commit**

If this is a git repo:

```bash
git add mathcounts_platform/server.py mathcounts_platform/views.py tests/test_views.py README.md
git commit -m "feat: add web routes and views"
```

## Task 8: Test-Taking UI And Styling

**Files:**
- Create: `static/styles.css`
- Create: `static/app.js`
- Modify: `mathcounts_platform/views.py`

**Step 1: Add view test for answer form**

Extend `tests/test_views.py`:

```python
def test_test_page_contains_answer_inputs(self):
    html = render_test_page(
        user={"email": "student@example.com"},
        year=2017,
        round_name="Sprint",
        resource={"url": "https://example.com/sprint"},
        answer_keys=[
            {"question_number": 1, "answer": "hidden", "points": 1},
            {"question_number": 2, "answer": "hidden", "points": 1},
        ],
        reference_links=[],
    )
    self.assertIn("name=\"answer_1\"", html)
    self.assertIn("name=\"answer_2\"", html)
    self.assertIn("Open paper in new tab", html)
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_views -v`

Expected: FAIL because `render_test_page` is incomplete.

**Step 3: Implement test page**

The test page should:

- Show the selected year and round.
- Show an iframe for the source paper when possible.
- Always show an `Open paper in new tab` fallback link.
- Render one input per answer-key question.
- Disable submit with a clear message if no answer keys exist.
- Include reference links for Answers/Solutions/Results/etc.

**Step 4: Add CSS**

Create a polished but simple layout:

- Dashboard cards by year.
- Two-column test page on desktop: paper viewer and answer sheet.
- Single-column layout on mobile.
- Clear result colors for correct and incorrect answers.

**Step 5: Run tests**

Run: `python3 -m unittest tests.test_views -v`

Expected: PASS.

**Step 6: Commit**

If this is a git repo:

```bash
git add static/styles.css static/app.js mathcounts_platform/views.py tests/test_views.py
git commit -m "feat: add test-taking interface"
```

## Task 9: Attempt Submission And History

**Files:**
- Modify: `mathcounts_platform/server.py`
- Modify: `mathcounts_platform/db.py`
- Modify: `mathcounts_platform/views.py`
- Create: `tests/test_attempt_flow.py`

**Step 1: Write failing integration-style unit test**

Test the core non-HTTP flow first:

```python
# tests/test_attempt_flow.py
import sqlite3
import unittest

from mathcounts_platform.db import (
    create_user,
    get_attempt_answers,
    get_attempts_for_user,
    migrate,
    upsert_answer_key,
)
from mathcounts_platform.grading import grade_answers
from mathcounts_platform.server import save_graded_attempt


class AttemptFlowTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_save_graded_attempt(self):
        user_id = create_user(self.conn, "student@example.com", "hash")
        upsert_answer_key(self.conn, 2017, "Sprint", 1, "42", 1)
        keys = [{"question_number": 1, "answer": "42", "points": 1}]
        grade = grade_answers(keys, {"1": "42"})

        attempt_id = save_graded_attempt(self.conn, user_id, 2017, "Sprint", {"1": "42"}, grade)

        self.assertEqual(get_attempts_for_user(self.conn, user_id)[0]["score"], 1)
        self.assertTrue(get_attempt_answers(self.conn, attempt_id)[0]["is_correct"])
```

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_attempt_flow -v`

Expected: FAIL because `save_graded_attempt` or DB helpers are missing.

**Step 3: Implement attempt save flow**

Implement:

- `get_attempt_answers(conn, attempt_id)` in `db.py`.
- `save_graded_attempt(conn, user_id, year, round_name, submitted_answers, grade)` in `server.py`.
- `POST /submit-attempt` route that parses form fields named `answer_N`, grades them, saves them, and redirects to `/history` or a result page.

**Step 4: Add result display**

Show:

- Score and max score.
- Per-question submitted answer.
- Correct answer.
- Correct/incorrect marker.

**Step 5: Run full tests**

Run: `python3 -m unittest -v`

Expected: PASS.

**Step 6: Commit**

If this is a git repo:

```bash
git add mathcounts_platform/server.py mathcounts_platform/db.py mathcounts_platform/views.py tests/test_attempt_flow.py
git commit -m "feat: grade and save test attempts"
```

## Task 10: App Initialization And Manual Verification

**Files:**
- Create: `scripts/init_db.py`
- Modify: `README.md`

**Step 1: Create initialization script**

`scripts/init_db.py` should:

- Create `data/app.sqlite3`.
- Run `migrate(conn)`.
- Load `data/catalog.json`.
- Seed resources.
- If an answer key CSV path is passed, import answer keys.

Usage:

```bash
python3 scripts/init_db.py
python3 scripts/init_db.py --answer-keys data/answer_keys.sample.csv
```

**Step 2: Run tests**

Run: `python3 -m unittest -v`

Expected: PASS.

**Step 3: Initialize database**

Run:

```bash
python3 scripts/init_db.py --answer-keys data/answer_keys.sample.csv
```

Expected: `data/app.sqlite3` exists and contains users/resources/answer_keys tables.

**Step 4: Start server**

Run:

```bash
python3 -m mathcounts_platform.server --host 127.0.0.1 --port 8000 --db data/app.sqlite3
```

Expected: The server starts and reports `http://127.0.0.1:8000`.

**Step 5: Verify with curl**

In another shell, run:

```bash
curl -i http://127.0.0.1:8000/login
```

Expected: HTTP 200 and HTML containing login form fields.

**Step 6: Manual browser check**

Open `http://127.0.0.1:8000`, register a user, choose a year/round, and verify:

- The year dashboard loads.
- Source paper link is present.
- Answer boxes appear when answer keys exist.
- Submission calculates and saves a score.
- History shows the saved attempt after logout/login.

**Step 7: Commit**

If this is a git repo:

```bash
git add README.md scripts/init_db.py
git commit -m "chore: add app initialization workflow"
```

## Post-MVP Follow-Ups

- Add a secure admin screen for uploading answer-key CSV files.
- Add PDF answer-key extraction if a PDF parser is installed or approved.
- Improve answer normalization for numeric equivalence, fractions, mixed numbers, units, and multiple acceptable answers.
- Add timers for Sprint, Target, and Team rounds.
- Add charts for progress by year and round.
