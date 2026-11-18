from pathlib import Path
import unittest

from mathcounts_platform.topics import SUBJECTS, load_problem_tags


TAGGED_YEARS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
ROUND_SIZES = {"Sprint": 30, "Target": 8, "Team": 10}


class ProblemTagDataTest(unittest.TestCase):
    def setUp(self):
        self.problems = load_problem_tags(Path("data/problem_tags.csv"))

    def test_every_local_year_problem_is_tagged_once(self):
        keys = [(p["year"], p["round"], p["question_number"]) for p in self.problems]
        self.assertEqual(len(keys), len(set(keys)))

        expected = {
            (year, round_name, number)
            for year in TAGGED_YEARS
            for round_name, size in ROUND_SIZES.items()
            for number in range(1, size + 1)
        }
        self.assertEqual(set(keys), expected)

    def test_tags_have_pages_and_every_subject_is_used(self):
        for problem in self.problems:
            self.assertIsNotNone(problem["page"], problem)
            self.assertTrue(problem["summary"], problem)
        self.assertEqual({p["subject"] for p in self.problems}, set(SUBJECTS))


if __name__ == "__main__":
    unittest.main()
