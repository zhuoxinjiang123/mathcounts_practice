"""Problem tags: subject + difficulty metadata for individual competition problems.

Tags live in ``data/problem_tags.csv`` so they can be reviewed and corrected by
hand. Difficulty is an estimate based on where a problem sits in its round
(MATHCOUNTS orders problems roughly easiest to hardest); the CSV column can
override it per problem.
"""

import csv
import io
import re
from functools import lru_cache
from pathlib import Path


DEFAULT_TAGS_PATH = Path("data/problem_tags.csv")

SUBJECTS = (
    "Algebra",
    "Geometry",
    "Number Theory",
    "Counting & Probability",
    "General Math",
)
DIFFICULTIES = ("Easy", "Medium", "Hard")
ROUNDS = ("Sprint", "Target", "Team")
STATUSES = {
    "new": "Not tried",
    "missed": "Missed",
    "solved": "Solved",
}

# Inclusive upper bound of the Easy and Medium bands for each round.
_DIFFICULTY_BANDS = {
    "Sprint": (10, 20),
    "Target": (2, 6),
    "Team": (3, 7),
}


def estimate_difficulty(round_name, question_number):
    easy_max, medium_max = _DIFFICULTY_BANDS.get(round_name, (0, 0))
    number = int(question_number)
    if number <= easy_max:
        return "Easy"
    if number <= medium_max:
        return "Medium"
    return "Hard"


def parse_problem_tags_csv(text):
    problems = []
    for row in csv.DictReader(io.StringIO(text)):
        round_name = row["round"].strip()
        question_number = int(row["question_number"])
        subject = row["subject"].strip()
        difficulty = (row.get("difficulty") or "").strip() or estimate_difficulty(round_name, question_number)
        if subject not in SUBJECTS:
            raise ValueError(f"Unknown subject {subject!r} for {row['year']} {round_name} #{question_number}")
        if difficulty not in DIFFICULTIES:
            raise ValueError(f"Unknown difficulty {difficulty!r} for {row['year']} {round_name} #{question_number}")
        page = (row.get("page") or "").strip()
        problems.append(
            {
                "year": int(row["year"]),
                "round": round_name,
                "question_number": question_number,
                "subject": subject,
                "difficulty": difficulty,
                "page": int(page) if page else None,
                "summary": (row.get("summary") or "").strip(),
            }
        )
    return sorted(problems, key=problem_sort_key)


@lru_cache(maxsize=4)
def _load_cached(path_str, mtime):
    return tuple(parse_problem_tags_csv(Path(path_str).read_text(encoding="utf-8")))


def load_problem_tags(path=DEFAULT_TAGS_PATH):
    path = Path(path)
    if not path.is_file():
        return []
    return list(_load_cached(str(path.resolve()), path.stat().st_mtime))


def problem_key(problem):
    return (int(problem["year"]), problem["round"], int(problem["question_number"]))


def problem_sort_key(problem):
    round_index = ROUNDS.index(problem["round"]) if problem["round"] in ROUNDS else len(ROUNDS)
    return (-int(problem["year"]), round_index, int(problem["question_number"]))


def find_problem(problems, year, round_name, question_number):
    wanted = (int(year), round_name, int(question_number))
    return next((problem for problem in problems if problem_key(problem) == wanted), None)


def clean_filters(raw):
    """Keep only recognised filter values so they are safe to echo back."""
    filters = {}
    for name, allowed in (
        ("subject", SUBJECTS),
        ("difficulty", DIFFICULTIES),
        ("round", ROUNDS),
        ("status", tuple(STATUSES)),
    ):
        value = (raw.get(name) or "").strip()
        if value in allowed:
            filters[name] = value
    return filters


def filter_problems(problems, filters, statuses=None):
    statuses = statuses or {}
    selected = []
    for problem in problems:
        if "subject" in filters and problem["subject"] != filters["subject"]:
            continue
        if "difficulty" in filters and problem["difficulty"] != filters["difficulty"]:
            continue
        if "round" in filters and problem["round"] != filters["round"]:
            continue
        if "status" in filters and status_for(problem, statuses) != filters["status"]:
            continue
        selected.append(problem)
    return selected


def group_problems(problems):
    """Group problems as {subject: {difficulty: [problems]}} in canonical order."""
    grouped = {}
    for subject in SUBJECTS:
        by_difficulty = {}
        for difficulty in DIFFICULTIES:
            matches = [p for p in problems if p["subject"] == subject and p["difficulty"] == difficulty]
            if matches:
                by_difficulty[difficulty] = matches
        if by_difficulty:
            grouped[subject] = by_difficulty
    return grouped


def status_for(problem, statuses):
    result = statuses.get(problem_key(problem))
    if result is None:
        return "new"
    return "solved" if result else "missed"


def subject_summary(problems, statuses):
    """Per-subject counts by difficulty plus how many the user tried and solved."""
    summary = []
    for subject in SUBJECTS:
        subject_problems = [p for p in problems if p["subject"] == subject]
        tried = [p for p in subject_problems if problem_key(p) in statuses]
        summary.append(
            {
                "subject": subject,
                "total": len(subject_problems),
                "by_difficulty": {
                    difficulty: sum(1 for p in subject_problems if p["difficulty"] == difficulty)
                    for difficulty in DIFFICULTIES
                },
                "tried": len(tried),
                "solved": sum(1 for p in tried if statuses[problem_key(p)]),
            }
        )
    return summary


def adjacent_problems(problems, current):
    """Previous and next problem around ``current`` in ``problems`` order.

    ``current`` may be absent from ``problems`` (for example after a status
    filter excludes a problem the user just solved), so neighbours are found by
    sort position rather than list index.
    """
    current_key = problem_sort_key(current)
    previous = None
    following = None
    for problem in problems:
        key = problem_sort_key(problem)
        if key < current_key:
            previous = problem
        elif key > current_key and following is None:
            following = problem
    return previous, following


def problem_page_url(paper_url, page):
    if not page:
        return paper_url
    base = paper_url.split("#", 1)[0]
    fragment = paper_url.split("#", 1)[1] if "#" in paper_url else ""
    if re.search(r"(^|&)page=\d+", fragment):
        fragment = re.sub(r"(^|&)page=\d+", rf"\g<1>page={int(page)}", fragment)
    else:
        fragment = f"page={int(page)}" + (f"&{fragment}" if fragment else "")
    return f"{base}#{fragment}"
