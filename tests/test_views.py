import unittest

from mathcounts_platform.views import render_dashboard_page, render_login_page, render_test_page


class ViewTest(unittest.TestCase):
    def test_login_page_contains_form(self):
        html = render_login_page(error=None)
        self.assertIn("<form", html)
        self.assertIn('name="email"', html)
        self.assertIn('name="password"', html)

    def test_dashboard_lists_years(self):
        html = render_dashboard_page(
            user={"email": "student@example.com"},
            years=[{"year": 2017}, {"year": 2016}],
            attempts=[],
        )
        self.assertIn("2017", html)
        self.assertIn("2016", html)

    def test_test_page_contains_answer_inputs(self):
        html = render_test_page(
            user={"email": "student@example.com"},
            year=2017,
            round_name="Sprint",
            resource={"url": "https://example.com/sprint"},
            answer_keys=[{"question_number": number, "answer": "hidden", "points": 1} for number in range(1, 31)],
            reference_links=[],
        )
        self.assertIn('name="answer_1"', html)
        self.assertIn('name="answer_30"', html)
        self.assertEqual(html.count('class="answer-row"'), 30)
        self.assertIn("1 point each", html)
        self.assertIn("Open paper in new tab", html)

    def test_target_page_contains_eight_answers_in_four_pairs(self):
        html = render_test_page(
            user={"email": "student@example.com"},
            year=2017,
            round_name="Target",
            resource={"url": "https://example.com/target"},
            answer_keys=[{"question_number": number, "answer": "hidden", "points": 2} for number in range(1, 9)],
            reference_links=[],
        )

        self.assertIn('name="answer_8"', html)
        self.assertEqual(html.count('class="answer-row"'), 8)
        self.assertIn("Pair 4", html)
        self.assertIn("2 points each", html)
