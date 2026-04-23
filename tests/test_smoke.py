import unittest

from mathcounts_platform import APP_NAME


class SmokeTest(unittest.TestCase):
    def test_app_name_exists(self):
        self.assertEqual(APP_NAME, "MATHCOUNTS National Practice")
