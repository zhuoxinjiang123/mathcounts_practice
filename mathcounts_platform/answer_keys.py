import csv
from io import StringIO

from mathcounts_platform.db import upsert_answer_key


REQUIRED_COLUMNS = {"year", "round", "question_number", "answer", "points"}
VALID_ROUNDS = {"Sprint", "Target", "Team"}


def parse_answer_key_csv(csv_text):
    reader = csv.DictReader(StringIO(csv_text))
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        missing = sorted(REQUIRED_COLUMNS - set(reader.fieldnames or []))
        raise ValueError(f"Missing required answer key columns: {', '.join(missing)}")

    rows = []
    for line_number, row in enumerate(reader, start=2):
        year = _positive_int(row.get("year"), "year", line_number)
        if year < 2000 or year > 2017:
            raise ValueError(f"Line {line_number}: year must be between 2000 and 2017")

        round_name = (row.get("round") or "").strip()
        if round_name not in VALID_ROUNDS:
            raise ValueError(f"Line {line_number}: round must be Sprint, Target, or Team")

        question_number = _positive_int(row.get("question_number"), "question_number", line_number)
        points = _positive_int(row.get("points"), "points", line_number)
        answer = (row.get("answer") or "").strip()
        if not answer:
            raise ValueError(f"Line {line_number}: answer is required")

        rows.append(
            {
                "year": year,
                "round": round_name,
                "question_number": question_number,
                "answer": answer,
                "points": points,
            }
        )
    return rows


def import_answer_keys(conn, rows):
    for row in rows:
        upsert_answer_key(
            conn,
            row["year"],
            row["round"],
            row["question_number"],
            row["answer"],
            row["points"],
        )


def _positive_int(value, field, line_number):
    try:
        parsed = int(str(value or "").strip())
    except ValueError as exc:
        raise ValueError(f"Line {line_number}: {field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"Line {line_number}: {field} must be a positive integer")
    return parsed
