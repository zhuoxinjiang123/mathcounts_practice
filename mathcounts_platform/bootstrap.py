import argparse
import json
import os
import sqlite3
from pathlib import Path

from mathcounts_platform.answer_keys import import_answer_keys, parse_answer_key_csv
from mathcounts_platform.catalog import seed_catalog
from mathcounts_platform.db import migrate


DEFAULT_DB_PATH = Path("data/app.sqlite3")
DEFAULT_CATALOG_PATH = Path("data/catalog.json")
DEFAULT_ANSWER_KEYS_PATH = Path("data/answer_keys.csv")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def init_database(
    db_path=DEFAULT_DB_PATH,
    catalog_path=DEFAULT_CATALOG_PATH,
    answer_keys_path=DEFAULT_ANSWER_KEYS_PATH,
):
    db_path = Path(db_path)
    catalog_path = Path(catalog_path)
    answer_keys_path = Path(answer_keys_path) if answer_keys_path else None
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate(conn)

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    seed_catalog(conn, catalog)

    imported_answers = 0
    if answer_keys_path:
        answer_rows = parse_answer_key_csv(answer_keys_path.read_text(encoding="utf-8"))
        import_answer_keys(conn, answer_rows)
        imported_answers = len(answer_rows)

    conn.close()
    return {"db_path": str(db_path), "catalog_years": len(catalog), "answer_keys": imported_answers}


def bootstrap_app(
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    db_path=DEFAULT_DB_PATH,
    catalog_path=DEFAULT_CATALOG_PATH,
    answer_keys_path=DEFAULT_ANSWER_KEYS_PATH,
    force_init=False,
    run_server=None,
):
    db_path = Path(db_path)
    catalog_path = Path(catalog_path)
    answer_keys_path = Path(answer_keys_path) if answer_keys_path else None

    if force_init or not db_path.exists():
        init_database(
            db_path=db_path,
            catalog_path=catalog_path,
            answer_keys_path=answer_keys_path,
        )

    if run_server is None:
        from mathcounts_platform.server import run as run_server

    run_server(host=host, port=int(port), db_path=db_path)


def config_from_environ(environ=None):
    environ = environ or os.environ
    return {
        "host": environ.get("MATHCOUNTS_HOST", DEFAULT_HOST),
        "port": int(environ.get("PORT", environ.get("MATHCOUNTS_PORT", str(DEFAULT_PORT)))),
        "db_path": Path(environ.get("MATHCOUNTS_DB_PATH", str(DEFAULT_DB_PATH))),
        "catalog_path": Path(environ.get("MATHCOUNTS_CATALOG_PATH", str(DEFAULT_CATALOG_PATH))),
        "answer_keys_path": Path(environ.get("MATHCOUNTS_ANSWER_KEYS_PATH", str(DEFAULT_ANSWER_KEYS_PATH))),
        "force_init": parse_bool(environ.get("MATHCOUNTS_FORCE_INIT", "")),
    }


def parse_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def main(environ=None):
    config = config_from_environ(environ)
    bootstrap_app(**config)


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH))
    parser.add_argument("--answer-keys", default=str(DEFAULT_ANSWER_KEYS_PATH))
    parser.add_argument("--force-init", action="store_true")
    args = parser.parse_args()
    bootstrap_app(
        host=args.host,
        port=args.port,
        db_path=args.db,
        catalog_path=args.catalog,
        answer_keys_path=args.answer_keys,
        force_init=args.force_init,
    )


if __name__ == "__main__":
    main()
