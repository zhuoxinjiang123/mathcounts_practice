from mathcounts_platform.rounds import round_point_value


def normalize_answer(value):
    return str(value or "").strip().casefold()


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
        is_correct = normalize_answer(submitted_answer) == normalize_answer(correct_answer)

        max_score += points
        if is_correct:
            score += points

        results.append(
            {
                "question_number": question_number,
                "submitted_answer": submitted_answer,
                "correct_answer": correct_answer,
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
