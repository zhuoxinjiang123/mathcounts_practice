import unittest

from mathcounts_platform.server import content_type_for_path


class ServerFilesTest(unittest.TestCase):
    def test_pdf_files_are_served_with_pdf_content_type(self):
        self.assertEqual(content_type_for_path("round.pdf"), "application/pdf")
