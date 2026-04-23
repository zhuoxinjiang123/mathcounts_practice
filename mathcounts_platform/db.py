import json


def migrate(conn):
    conn.executescript(
        """
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

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL REFERENCES users(id),
          token_hash TEXT NOT NULL UNIQUE,
          expires_at TEXT NOT NULL,
          used_at TEXT,
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
        """
    )
    conn.commit()


def create_user(conn, email, password_hash):
    cursor = conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, password_hash),
    )
    conn.commit()
    return cursor.lastrowid


def get_user_by_email(conn, email):
    return conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()


def update_user_password(conn, user_id, password_hash):
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, int(user_id)),
    )
    conn.commit()


def upsert_resource(conn, year, label, kind, url, gradable):
    conn.execute(
        """
        INSERT INTO resources (year, label, kind, url, gradable)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(year, label, kind) DO UPDATE SET
          url = excluded.url,
          gradable = excluded.gradable
        """,
        (int(year), label, kind, url, int(bool(gradable))),
    )
    conn.commit()


def upsert_answer_key(conn, year, round_name, question_number, answer, points):
    conn.execute(
        """
        INSERT INTO answer_keys (year, round, question_number, answer, points)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(year, round, question_number) DO UPDATE SET
          answer = excluded.answer,
          points = excluded.points
        """,
        (int(year), round_name, int(question_number), str(answer), int(points)),
    )
    conn.commit()


def get_years(conn):
    return conn.execute(
        """
        SELECT DISTINCT year
        FROM resources
        ORDER BY year DESC
        """
    ).fetchall()


def get_gradable_resource(conn, year, round_name):
    return conn.execute(
        """
        SELECT * FROM resources
        WHERE year = ? AND label = ? AND gradable = 1
        """,
        (int(year), round_name),
    ).fetchone()


def get_reference_resources(conn, year):
    return conn.execute(
        """
        SELECT * FROM resources
        WHERE year = ? AND gradable = 0
        ORDER BY id
        """,
        (int(year),),
    ).fetchall()


def get_answer_keys(conn, year, round_name):
    return conn.execute(
        """
        SELECT * FROM answer_keys
        WHERE year = ? AND round = ?
        ORDER BY question_number
        """,
        (int(year), round_name),
    ).fetchall()


def create_attempt(
    conn,
    user_id,
    year,
    round_name,
    submitted_answers,
    per_question_results,
    score,
    max_score,
):
    cursor = conn.execute(
        """
        INSERT INTO attempts (
          user_id, year, round, submitted_answers_json, score, max_score
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            int(year),
            round_name,
            json.dumps(submitted_answers, sort_keys=True),
            int(score),
            int(max_score),
        ),
    )
    attempt_id = cursor.lastrowid

    conn.executemany(
        """
        INSERT INTO attempt_answers (
          attempt_id, question_number, submitted_answer, correct_answer, points, is_correct
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                attempt_id,
                int(result["question_number"]),
                str(result.get("submitted_answer", "")),
                str(result.get("correct_answer", "")),
                int(result.get("points", 1)),
                int(bool(result.get("is_correct"))),
            )
            for result in per_question_results
        ],
    )
    conn.commit()
    return attempt_id


def get_attempts_for_user(conn, user_id):
    return conn.execute(
        """
        SELECT * FROM attempts
        WHERE user_id = ?
        ORDER BY submitted_at DESC, id DESC
        """,
        (int(user_id),),
    ).fetchall()


def get_attempt(conn, user_id, attempt_id):
    return conn.execute(
        """
        SELECT * FROM attempts
        WHERE id = ? AND user_id = ?
        """,
        (int(attempt_id), int(user_id)),
    ).fetchone()


def get_attempt_answers(conn, attempt_id):
    return conn.execute(
        """
        SELECT * FROM attempt_answers
        WHERE attempt_id = ?
        ORDER BY question_number
        """,
        (int(attempt_id),),
    ).fetchall()


def get_user_for_session(conn, token):
    from mathcounts_platform.auth import hash_token

    return conn.execute(
        """
        SELECT users.*
        FROM users
        JOIN sessions ON sessions.user_id = users.id
        WHERE sessions.token_hash = ?
          AND sessions.expires_at > CURRENT_TIMESTAMP
        """,
        (hash_token(token),),
    ).fetchone()


def get_user_for_password_reset_token(conn, token):
    from mathcounts_platform.auth import hash_token

    return conn.execute(
        """
        SELECT users.*
        FROM users
        JOIN password_reset_tokens ON password_reset_tokens.user_id = users.id
        WHERE password_reset_tokens.token_hash = ?
          AND password_reset_tokens.used_at IS NULL
          AND password_reset_tokens.expires_at > CURRENT_TIMESTAMP
        """,
        (hash_token(token),),
    ).fetchone()


def mark_password_reset_token_used(conn, token):
    from mathcounts_platform.auth import hash_token

    conn.execute(
        """
        UPDATE password_reset_tokens
        SET used_at = CURRENT_TIMESTAMP
        WHERE token_hash = ?
        """,
        (hash_token(token),),
    )
    conn.commit()
