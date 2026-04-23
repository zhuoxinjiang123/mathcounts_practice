import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mathcounts_platform.answer_keys import import_answer_keys, parse_answer_key_csv
from mathcounts_platform.catalog import seed_catalog
from mathcounts_platform.db import migrate


DEFAULT_DB_PATH = Path("data/app.sqlite3")
DEFAULT_CATALOG_PATH = Path("data/catalog.json")


def init_database(db_path=DEFAULT_DB_PATH, catalog_path=DEFAULT_CATALOG_PATH, answer_keys_path=None):
    db_path = Path(db_path)
    catalog_path = Path(catalog_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate(conn)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    seed_catalog(conn, catalog)

    imported_answers = 0
    if answer_keys_path:
        answer_rows = parse_answer_key_csv(Path(answer_keys_path).read_text(encoding="utf-8"))
        import_answer_keys(conn, answer_rows)
        imported_answers = len(answer_rows)

    conn.close()
    return {"db_path": str(db_path), "catalog_years": len(catalog), "answer_keys": imported_answers}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH))
    parser.add_argument("--answer-keys")
    args = parser.parse_args()

    result = init_database(args.db, args.catalog, args.answer_keys)
    print(
        "Initialized {db_path} with {catalog_years} catalog years and {answer_keys} answer keys.".format(
            **result
        )
    )


if __name__ == "__main__":
    main()
