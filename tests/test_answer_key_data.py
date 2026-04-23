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

    def test_recent_national_years_have_complete_answer_keys(self):
        rows = parse_answer_key_csv(Path("data/answer_keys.csv").read_text(encoding="utf-8"))
        keyed = {
            (row["year"], row["round"], row["question_number"]): row["answer"]
            for row in rows
        }

        for year in (2018, 2019, 2021, 2022, 2023, 2024, 2025):
            for question_number in range(1, 31):
                self.assertIn((year, "Sprint", question_number), keyed)
            for question_number in range(1, 9):
                self.assertIn((year, "Target", question_number), keyed)
            for question_number in range(1, 11):
                self.assertIn((year, "Team", question_number), keyed)

        self.assertEqual(keyed[(2025, "Sprint", 1)], "24")
        self.assertEqual(keyed[(2024, "Target", 2)], "sqrt(193) cm||sqrt(193)")
