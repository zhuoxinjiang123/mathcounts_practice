import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from mathcounts_platform import bootstrap


class BootstrapTest(unittest.TestCase):
    def test_bootstrap_initializes_database_when_missing(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "app.sqlite3"
            catalog_path = Path(tempdir) / "catalog.json"
            answer_keys_path = Path(tempdir) / "answer_keys.csv"
            runner = Mock()

            with patch.object(bootstrap, "init_database") as init_database:
                bootstrap.bootstrap_app(
                    host="0.0.0.0",
                    port=8000,
                    db_path=db_path,
                    catalog_path=catalog_path,
                    answer_keys_path=answer_keys_path,
                    run_server=runner,
                )

            init_database.assert_called_once_with(
                db_path=db_path,
                catalog_path=catalog_path,
                answer_keys_path=answer_keys_path,
            )
            runner.assert_called_once_with(host="0.0.0.0", port=8000, db_path=db_path)

    def test_bootstrap_skips_initialization_when_database_exists(self):
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = Path(tempdir) / "app.sqlite3"
            db_path.write_text("existing", encoding="utf-8")
            runner = Mock()

            with patch.object(bootstrap, "init_database") as init_database:
                bootstrap.bootstrap_app(db_path=db_path, run_server=runner)

            init_database.assert_not_called()
            runner.assert_called_once_with(host="127.0.0.1", port=8000, db_path=db_path)

    def test_config_from_environ_reads_docker_friendly_values(self):
        config = bootstrap.config_from_environ(
            {
                "MATHCOUNTS_HOST": "0.0.0.0",
                "PORT": "9000",
                "MATHCOUNTS_DB_PATH": "/tmp/docker-data/app.sqlite3",
                "MATHCOUNTS_CATALOG_PATH": "/tmp/catalog.json",
                "MATHCOUNTS_ANSWER_KEYS_PATH": "/tmp/answer_keys.csv",
                "MATHCOUNTS_FORCE_INIT": "true",
            }
        )

        self.assertEqual(config["host"], "0.0.0.0")
        self.assertEqual(config["port"], 9000)
        self.assertEqual(config["db_path"], Path("/tmp/docker-data/app.sqlite3"))
        self.assertEqual(config["catalog_path"], Path("/tmp/catalog.json"))
        self.assertEqual(config["answer_keys_path"], Path("/tmp/answer_keys.csv"))
        self.assertTrue(config["force_init"])


if __name__ == "__main__":
    unittest.main()
