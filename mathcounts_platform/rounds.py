ROUND_CONFIGS = {
    "Sprint": {
        "question_count": 30,
        "points": 1,
        "description": "30 questions, 1 point each",
    },
    "Target": {
        "question_count": 8,
        "points": 2,
        "description": "8 questions in 4 pairs, 2 points each",
        "group_size": 2,
        "group_label": "Pair",
    },
}


def round_config(round_name):
    return ROUND_CONFIGS.get(round_name)


def round_question_numbers(round_name, answer_keys=()):
    config = round_config(round_name)
    if config:
        return list(range(1, config["question_count"] + 1))
    return [int(_field(key, "question_number")) for key in answer_keys]


def round_point_value(round_name, question_number=None, fallback=1):
    config = round_config(round_name)
    if config:
        return int(config["points"])
    return int(fallback)


def round_description(round_name):
    config = round_config(round_name)
    if not config:
        return ""
    return config["description"]


def round_group_label(round_name, question_number):
    config = round_config(round_name)
    if not config or not config.get("group_size"):
        return ""
    group_number = ((int(question_number) - 1) // int(config["group_size"])) + 1
    return f"{config.get('group_label', 'Group')} {group_number}"


def is_answer_key_complete(round_name, answer_keys):
    expected_numbers = set(round_question_numbers(round_name, answer_keys))
    keyed_numbers = {int(_field(key, "question_number")) for key in answer_keys}
    return bool(expected_numbers) and expected_numbers.issubset(keyed_numbers)


def _field(row, name, default=None):
    try:
        return row[name]
    except (IndexError, KeyError, TypeError):
        if hasattr(row, "get"):
            return row.get(name, default)
        return default
