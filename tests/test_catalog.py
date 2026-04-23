import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from mathcounts_platform.catalog import parse_national_resources


class CatalogTest(unittest.TestCase):
    def test_parse_national_resources(self):
        html = """
        <div class="paragraph"><strong><font size="6">2017</font></strong><br />
        <strong>NATIONAL: &nbsp;&nbsp;</strong>
        <a href="https://example.com/sprint" target="_blank">Sprint</a>&nbsp;|&nbsp;
        <a href="https://example.com/answers" target="_blank">Answers</a>
        </div>
        """

        catalog = parse_national_resources(html)

        self.assertEqual(catalog[0]["year"], 2017)
        self.assertEqual(catalog[0]["resources"][0]["label"], "Sprint")
        self.assertTrue(catalog[0]["resources"][0]["gradable"])
        self.assertFalse(catalog[0]["resources"][1]["gradable"])

    def test_build_catalog_script_runs_from_project_root(self):
        fixture = Path("tests/fixtures/mathcounts_sample.html")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "catalog.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/build_catalog.py",
                    str(fixture),
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
