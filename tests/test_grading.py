import unittest

from mathcounts_platform.grading import answer_options, grade_answers, normalize_answer


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

    def test_sprint_and_target_use_fixed_round_points(self):
        keys = [
            {"round": "Sprint", "question_number": 1, "answer": "A", "points": 99},
            {"round": "Target", "question_number": 1, "answer": "B", "points": 99},
        ]

        result = grade_answers(keys, {"1": "B"})

        self.assertEqual(result["score"], 2)
        self.assertEqual(result["max_score"], 3)

    def test_grades_against_accepted_answer_variants_but_displays_official_answer(self):
        keys = [
            {"round": "Sprint", "question_number": 1, "answer": "5600 gallons||5600", "points": 1},
        ]

        result = grade_answers(keys, {"1": "5600"})

        self.assertEqual(result["score"], 1)
        self.assertEqual(result["results"][0]["correct_answer"], "5600 gallons")

    def test_answer_options_ignore_blank_variants(self):
        self.assertEqual(answer_options("A|| ||B"), ["A", "B"])
