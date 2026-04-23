import sqlite3
import unittest

from mathcounts_platform.db import (
    create_user,
    get_answer_keys,
    get_attempt_answers,
    get_attempts_for_user,
    migrate,
    upsert_answer_key,
)
from mathcounts_platform.grading import grade_answers
from mathcounts_platform.server import load_attempt_results, save_graded_attempt


class AttemptFlowTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_save_graded_attempt(self):
        user_id = create_user(self.conn, "student@example.com", "hash")
        upsert_answer_key(self.conn, 2017, "Sprint", 1, "42", 1)
        keys = get_answer_keys(self.conn, 2017, "Sprint")
        grade = grade_answers(keys, {"1": "42"})

        attempt_id = save_graded_attempt(self.conn, user_id, 2017, "Sprint", {"1": "42"}, grade)

        self.assertEqual(get_attempts_for_user(self.conn, user_id)[0]["score"], 1)
        self.assertTrue(get_attempt_answers(self.conn, attempt_id)[0]["is_correct"])

    def test_results_use_current_answer_key_for_stale_saved_attempts(self):
        user_id = create_user(self.conn, "student@example.com", "hash")
        for question_number in range(1, 31):
            upsert_answer_key(self.conn, 2017, "Sprint", question_number, "example", 1)
        stale_grade = grade_answers(get_answer_keys(self.conn, 2017, "Sprint"), {"1": "42"})
        attempt_id = save_graded_attempt(self.conn, user_id, 2017, "Sprint", {"1": "42"}, stale_grade)
        upsert_answer_key(self.conn, 2017, "Sprint", 1, "42", 1)

        attempt, results = load_attempt_results(self.conn, user_id, attempt_id)

        self.assertEqual(attempt["score"], 1)
        self.assertEqual(results[0]["correct_answer"], "42")
        self.assertTrue(results[0]["is_correct"])
