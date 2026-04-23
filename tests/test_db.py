import sqlite3
import unittest

from mathcounts_platform.db import (
    create_attempt,
    create_user,
    get_answer_keys,
    get_attempts_for_user,
    get_gradable_resource,
    get_reference_resources,
    get_user_by_email,
    get_years,
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
            [
                {
                    "question_number": 1,
                    "submitted_answer": "42",
                    "correct_answer": "42",
                    "points": 1,
                    "is_correct": True,
                }
            ],
            1,
            1,
        )

        self.assertEqual(get_user_by_email(self.conn, "student@example.com")["id"], user_id)
        self.assertEqual(keys[0]["answer"], "42")
        self.assertEqual(get_attempts_for_user(self.conn, user_id)[0]["id"], attempt_id)

    def test_year_and_resource_queries(self):
        upsert_resource(self.conn, 2017, "Sprint", "paper", "https://example.com/sprint", True)
        upsert_resource(self.conn, 2017, "Answers", "reference", "https://example.com/answers", False)
        upsert_resource(self.conn, 2016, "Team", "paper", "https://example.com/team", True)

        self.assertEqual([row["year"] for row in get_years(self.conn)], [2017, 2016])
        self.assertEqual(get_gradable_resource(self.conn, 2017, "Sprint")["url"], "https://example.com/sprint")
        self.assertEqual(get_reference_resources(self.conn, 2017)[0]["label"], "Answers")
