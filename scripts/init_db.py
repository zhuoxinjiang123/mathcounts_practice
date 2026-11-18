import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mathcounts_platform.bootstrap import (
    DEFAULT_CATALOG_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_ANSWER_KEYS_PATH,
    init_database,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG_PATH))
    parser.add_argument("--answer-keys", default=str(DEFAULT_ANSWER_KEYS_PATH))
    args = parser.parse_args()

    result = init_database(args.db, args.catalog, args.answer_keys)
    print(
        "Initialized {db_path} with {catalog_years} catalog years and {answer_keys} answer keys.".format(
            **result
        )
    )


if __name__ == "__main__":
    main()
