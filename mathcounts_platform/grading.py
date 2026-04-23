import re

from mathcounts_platform.rounds import round_point_value


def normalize_answer(value):
    normalized = str(value or "").strip().casefold()
    for old, new in {
        "−": "-",
        "–": "-",
        "—": "-",
        "√": "sqrt",
        "²": "^2",
    }.items():
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*([+\-*/^()])\s*", r"\1", normalized)
    return normalized


def answer_options(correct_answer):
    return [option.strip() for option in str(correct_answer or "").split("||") if option.strip()]


def display_answer(correct_answer):
    options = answer_options(correct_answer)
    return options[0] if options else ""


def answer_matches(submitted_answer, correct_answer):
    normalized_submitted = normalize_answer(submitted_answer)
    return any(normalized_submitted == normalize_answer(option) for option in answer_options(correct_answer))


def grade_answers(answer_keys, submitted_answers):
    results = []
    score = 0
    max_score = 0

    for key in sorted(answer_keys, key=lambda row: int(_field(row, "question_number"))):
        question_number = int(_field(key, "question_number"))
        round_name = _field(key, "round")
        points = round_point_value(round_name, question_number, _field(key, "points", 1))
        correct_answer = _field(key, "answer")
        submitted_answer = submitted_answers.get(str(question_number), "")
        is_correct = answer_matches(submitted_answer, correct_answer)

        max_score += points
        if is_correct:
            score += points

        results.append(
            {
                "question_number": question_number,
                "submitted_answer": submitted_answer,
                "correct_answer": display_answer(correct_answer),
                "points": points,
                "is_correct": is_correct,
            }
        )

    return {"score": score, "max_score": max_score, "results": results}


def _field(row, name, default=None):
    try:
        return row[name]
    except (IndexError, KeyError, TypeError):
        if hasattr(row, "get"):
            return row.get(name, default)
        return default
