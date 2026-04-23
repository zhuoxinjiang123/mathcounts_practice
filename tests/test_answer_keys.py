import sqlite3
import unittest

from mathcounts_platform.answer_keys import import_answer_keys, parse_answer_key_csv
from mathcounts_platform.db import get_answer_keys, migrate


class AnswerKeyImportTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)

    def test_parse_and_import_answer_keys(self):
        csv_text = "year,round,question_number,answer,points\n2017,Sprint,1,42,1\n2017,Target,1,B,2\n"
        rows = parse_answer_key_csv(csv_text)
        import_answer_keys(self.conn, rows)

        sprint_keys = get_answer_keys(self.conn, 2017, "Sprint")
        self.assertEqual(sprint_keys[0]["answer"], "42")
        self.assertEqual(sprint_keys[0]["points"], 1)

    def test_parse_recent_national_answer_key_years(self):
        csv_text = "year,round,question_number,answer,points\n2025,Sprint,1,24,1\n"

        rows = parse_answer_key_csv(csv_text)

        self.assertEqual(rows[0]["year"], 2025)
