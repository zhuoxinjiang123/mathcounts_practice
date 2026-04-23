import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mathcounts_platform.catalog import parse_national_resources


def main(argv):
    if len(argv) != 3:
        raise SystemExit("Usage: python3 scripts/build_catalog.py SOURCE_HTML OUTPUT_JSON")

    source_path = Path(argv[1])
    output_path = Path(argv[2])
    catalog = parse_national_resources(source_path.read_text(encoding="utf-8", errors="ignore"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog)} years to {output_path}")


if __name__ == "__main__":
    main(sys.argv)
