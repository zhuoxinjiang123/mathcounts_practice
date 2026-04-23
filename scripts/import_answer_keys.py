import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mathcounts_platform.answer_keys import import_answer_keys, parse_answer_key_csv
from mathcounts_platform.db import migrate


def main(argv):
    if len(argv) != 3:
        raise SystemExit("Usage: python3 scripts/import_answer_keys.py DATABASE_PATH ANSWER_KEYS_CSV")

    db_path = Path(argv[1])
    csv_path = Path(argv[2])
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    rows = parse_answer_key_csv(csv_path.read_text(encoding="utf-8"))
    import_answer_keys(conn, rows)
    print(f"Imported {len(rows)} answer keys into {db_path}")


if __name__ == "__main__":
    main(sys.argv)
