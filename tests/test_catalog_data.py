import json
from pathlib import Path
import unittest


class CatalogDataTest(unittest.TestCase):
    def test_catalog_includes_recent_national_years_from_local_papers(self):
        catalog = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
        by_year = {entry["year"]: entry for entry in catalog}

        for year in (2018, 2019, 2021, 2022, 2023, 2024, 2025):
            self.assertIn(year, by_year)
            resources = {resource["label"]: resource for resource in by_year[year]["resources"]}
            self.assertEqual({"Sprint", "Target", "Team", "Answers"}, set(resources))
            self.assertTrue(resources["Sprint"]["url"].startswith("/past_paper/"))
            self.assertIn("#page=", resources["Sprint"]["url"])
            self.assertIn("#page=", resources["Target"]["url"])
            self.assertIn("#page=", resources["Team"]["url"])
            self.assertIn("#page=", resources["Answers"]["url"])
            self.assertTrue(resources["Sprint"]["gradable"])
            self.assertTrue(resources["Target"]["gradable"])
            self.assertTrue(resources["Team"]["gradable"])
            self.assertFalse(resources["Answers"]["gradable"])
