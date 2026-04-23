from pathlib import Path
import unittest

from mathcounts_platform.answer_keys import parse_answer_key_csv


class AnswerKeyDataTest(unittest.TestCase):
    def test_official_answer_key_data_is_not_placeholder_content(self):
        rows = parse_answer_key_csv(Path("data/answer_keys.csv").read_text(encoding="utf-8"))

        self.assertFalse(any(row["answer"] == "example" for row in rows))

    def test_2017_national_sprint_contains_verified_official_answers(self):
        rows = parse_answer_key_csv(Path("data/answer_keys.csv").read_text(encoding="utf-8"))
        keyed = {
            (row["year"], row["round"], row["question_number"]): row["answer"]
            for row in rows
        }

        self.assertEqual(keyed[(2017, "Sprint", 7)], "-4")
        self.assertEqual(keyed[(2017, "Sprint", 30)], "2 - sqrt(3) units||2-sqrt(3)||2 - sqrt(3)")
        self.assertEqual(keyed[(2017, "Target", 7)], "sqrt(42) - 5 or -5 + sqrt(42)||sqrt(42) - 5||-5 + sqrt(42)")
