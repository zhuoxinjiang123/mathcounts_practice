"""Generate new practice problems similar to a tagged competition problem.

A problem is generated with the DeepSeek chat API (OpenAI-compatible), then a
second, independent call solves it from scratch. The problem is only accepted
when both answers agree, which filters out most generated problems whose stated
answer is wrong.
"""

import ast
import json
import math
import operator
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from mathcounts_platform.grading import answer_matches, normalize_answer


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_MAX_TOKENS = 8000
MAX_GENERATION_TRIES = 3
GENERATION_TIME_BUDGET_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 120

ROUND_CONTEXT = {
    "Sprint": "a Sprint Round problem (no calculator, about 1-2 minutes per problem)",
    "Target": "a Target Round problem (calculator allowed, about 3 minutes per problem)",
    "Team": "a Team Round problem (calculator allowed, solved collaboratively)",
}

DIFFICULTY_CONTEXT = {
    "Easy": (
        "an early problem in a MATHCOUNTS National round: one or two steps applying a single idea, "
        "but still a real competition problem, not a textbook drill"
    ),
    "Medium": (
        "a middle problem in a MATHCOUNTS National round: about three or four steps, or two ideas "
        "combined, with at least one step that needs some thought"
    ),
    "Hard": (
        "one of the hardest problems in a MATHCOUNTS National round: several steps and a non-obvious "
        "key insight, so a strong student needs several minutes. A one-step or routine problem is NOT acceptable"
    ),
}

ROUND_SIZES = {"Sprint": 30, "Target": 8, "Team": 10}


class GeneratorError(Exception):
    """A user-presentable failure while generating a problem."""


class GeneratorNotConfigured(GeneratorError):
    pass


class GeneratorFormatError(GeneratorError):
    """The model replied, but not with usable JSON (e.g. it ran out of tokens). Worth retrying."""


def load_dotenv(path=".env", environ=None):
    """Load KEY=VALUE lines into the environment without overriding existing values."""
    environ = os.environ if environ is None else environ
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if value[:1] in {'"', "'"} and value.count(value[0]) >= 2:
            value = value[1 : value.index(value[0], 1)]
        else:
            value = value.split(" #", 1)[0].strip()
        if key and key not in environ:
            environ[key] = value


class DeepSeekClient:
    def __init__(
        self,
        api_key,
        model=DEFAULT_MODEL,
        base_url=DEFAULT_BASE_URL,
        max_tokens=DEFAULT_MAX_TOKENS,
        generate_thinking=None,
        transport=None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = int(max_tokens)
        # None leaves the model's default. False/True is sent as vLLM's
        # chat_template_kwargs, which self-hosted DeepSeek servers understand.
        self.generate_thinking = generate_thinking
        self.transport = transport or _urllib_transport

    @classmethod
    def from_environ(cls, environ=None):
        environ = os.environ if environ is None else environ
        api_key = environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise GeneratorNotConfigured(
                "Problem generation needs a DeepSeek API key. Add DEEPSEEK_API_KEY to the .env file and restart the app."
            )
        thinking = environ.get("DEEPSEEK_GENERATE_THINKING", "").strip().lower()
        try:
            max_tokens = int(environ.get("DEEPSEEK_MAX_TOKENS", "") or DEFAULT_MAX_TOKENS)
        except ValueError:
            max_tokens = DEFAULT_MAX_TOKENS
        return cls(
            api_key=api_key,
            model=environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            base_url=environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
            max_tokens=max_tokens,
            generate_thinking={"on": True, "off": False}.get(thinking),
        )

    def chat_json(self, messages, temperature, thinking=None):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if "reasoner" not in self.model:
            payload["response_format"] = {"type": "json_object"}
        if thinking is not None:
            payload["chat_template_kwargs"] = {"thinking": bool(thinking)}
        response = self.transport(
            f"{self.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
        )
        try:
            choice = response["choices"][0]
            content = choice["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError):
            raise GeneratorError("DeepSeek returned an unexpected response.") from None
        if not content.strip():
            if choice.get("finish_reason") == "length":
                raise GeneratorFormatError("DeepSeek ran out of tokens before answering.")
            raise GeneratorFormatError("DeepSeek returned an empty response.")
        return parse_json_content(content)


def _urllib_transport(url, headers, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise GeneratorError(_http_error_message(error.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise GeneratorError("Could not reach DeepSeek. Check your internet connection and try again.") from None
    except json.JSONDecodeError:
        raise GeneratorError("DeepSeek returned an unreadable response.") from None


def _http_error_message(status):
    return {
        401: "DeepSeek rejected the API key. Check DEEPSEEK_API_KEY in the .env file.",
        402: "The DeepSeek account is out of balance. Top it up and try again.",
        429: "DeepSeek is rate limiting requests. Wait a moment and try again.",
    }.get(status, f"DeepSeek returned an error (HTTP {status}). Try again shortly.")


def parse_json_content(content):
    text = str(content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    elif not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise GeneratorFormatError("DeepSeek returned a problem in an unexpected format.") from None
    if not isinstance(data, dict):
        raise GeneratorFormatError("DeepSeek returned a problem in an unexpected format.")
    return data


def build_generation_messages(source):
    system = (
        "You write original competition math problems for middle school students preparing for "
        "MATHCOUNTS Nationals. Every problem must have exactly one correct answer, be fully "
        "solvable from its text alone (no figures or diagrams), and have a short numerical or "
        "simple-expression answer. Respond with JSON only."
    )
    summary = source.get("summary") or "(no description available)"
    user = f"""Write ONE new problem for a student to practice.

Model it on this real MATHCOUNTS National problem:
- Subject: {source["subject"]}
- Difficulty: {source["difficulty"]}, meaning {DIFFICULTY_CONTEXT[source["difficulty"]]}
- Format: {ROUND_CONTEXT.get(source["round"], "a competition problem")}; it was problem {int(source["question_number"])} of {ROUND_SIZES.get(source["round"], "?")} in its round
- What the original asks: {summary}

Requirements:
- Test the same core idea and need about the same amount of insight and work, but use a fresh scenario and different numbers. Do not copy the original.
- It must have one well-defined answer that can be computed exactly. Avoid questions about infinite families, "all possible values" over unbounded sets, or anything that needs a proof.
- Choose the numbers so the work comes out cleanly, and solve it yourself to make sure your answer is right before writing it.
- Describe any geometric figure completely in words.
- Write math in plain text with Unicode where helpful (for example √, π, ², ×, ≤). Do not use LaTeX.
- If the answer is not an integer, say how to express it (for example "as a common fraction" or "in simplest radical form" or "to the nearest tenth"), as MATHCOUNTS does.

Return JSON with exactly these keys:
{{
  "problem": "the full problem statement",
  "answer": "the final answer only, with no units, in plain ASCII such as 12, 3/4, 2sqrt(3), 5pi, -7, 0.25",
  "unit": "unit word(s) for the answer, or an empty string",
  "solution": "a concise solution sketch (at most about 100 words)"
}}"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_solver_messages(problem_text):
    system = (
        "You are an expert competition math solver and a strict problem reviewer. Solve the "
        "problem carefully, double-check your arithmetic, and respond with JSON only."
    )
    rubric = "; ".join(f"{level}: {description}" for level, description in DIFFICULTY_CONTEXT.items())
    user = f"""Solve this problem, then review it.

{problem_text}

Return JSON with exactly these keys:
{{
  "well_posed": true or false (false if anything is contradictory, ambiguous, factually wrong, has more than one possible answer, or needs a figure that isn't described),
  "issues": "what is wrong if well_posed is false, otherwise an empty string",
  "difficulty": "Easy", "Medium", or "Hard" for a MATHCOUNTS National round, judged by this scale: {rubric}
  "solution": "a clear step-by-step solution a middle school student can follow, written in plain text with Unicode math (no LaTeX), at most about 150 words",
  "answer": "the final answer only, with no units, in plain ASCII such as 12, 3/4, 2sqrt(3), 5pi, -7, 0.25"
}}"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def generate_similar_problem(
    source,
    client,
    tries=MAX_GENERATION_TRIES,
    time_budget=GENERATION_TIME_BUDGET_SECONDS,
    clock=time.monotonic,
):
    """Return a verified problem dict: problem, answer, unit, solution.

    No new attempt starts once ``time_budget`` seconds have passed.
    """
    thinking = getattr(client, "generate_thinking", None)
    started = clock()
    for attempt in range(tries):
        if attempt and clock() - started > time_budget:
            break
        try:
            generated = client.chat_json(build_generation_messages(source), temperature=1.0, thinking=thinking)
            problem_text = str(generated.get("problem", "")).strip()
            answer = str(generated.get("answer", "")).strip()
            if not problem_text or not answer:
                continue
            solved = client.chat_json(build_solver_messages(problem_text), temperature=0.0)
        except GeneratorFormatError:
            continue
        if not passes_review(solved, source["difficulty"]):
            continue
        if answers_equivalent(answer, str(solved.get("answer", ""))):
            # Prefer the verifier's solution: it was written for the final problem
            # text, while the generator's sketch can describe an earlier draft.
            solution = str(solved.get("solution", "") or "").strip() or str(generated.get("solution", "") or "").strip()
            return {
                "problem": problem_text,
                "answer": answer,
                "unit": str(generated.get("unit", "") or "").strip(),
                "solution": solution,
            }
    raise GeneratorError(
        "Couldn't produce a problem whose answer checked out after a few tries. Please try again."
    )


_DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def passes_review(solved, target_difficulty):
    """Reject problems the verifier flags as flawed or rates two levels too easy."""
    well_posed = solved.get("well_posed", True)
    if well_posed is False or str(well_posed).strip().lower() in {"false", "no", "0"}:
        return False
    rated = _DIFFICULTY_RANK.get(str(solved.get("difficulty", "")).strip().lower())
    target = _DIFFICULTY_RANK.get(str(target_difficulty).strip().lower())
    if rated is not None and target is not None and target - rated >= 2:
        return False
    return True


def accepted_answers(answer, unit=""):
    """Answer-key string (|| separated) accepting the answer with or without its unit."""
    options = [answer]
    if unit:
        options.append(f"{answer} {unit}")
    return "||".join(options)


def check_generated_answer(submitted, answer, unit=""):
    if answer_matches(submitted, accepted_answers(answer, unit)):
        return True
    submitted_text = str(submitted or "").strip()
    if unit and submitted_text.casefold().endswith(unit.casefold()):
        submitted_text = submitted_text[: -len(unit)].strip()
    # Accept equivalent exact forms only when both parse to the same value,
    # e.g. "2*sqrt(3)" for "2sqrt(3)", but not 0.75 for "3/4" style answers.
    return _same_form(submitted_text, answer) and answers_equivalent(submitted_text, answer)


def _same_form(left, right):
    def has_decimal(value):
        return "." in str(value)

    return has_decimal(left) == has_decimal(right)


def answers_equivalent(left, right):
    if normalize_answer(left) == normalize_answer(right) and normalize_answer(left):
        return True
    left_value = evaluate_answer(left)
    right_value = evaluate_answer(right)
    if left_value is None or right_value is None:
        return False
    return math.isclose(left_value, right_value, rel_tol=1e-9, abs_tol=1e-9)


_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY_OPERATORS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def evaluate_answer(value):
    """Safely evaluate a simple numeric answer such as '2sqrt(3)', '3/4', '5pi', '1,024'."""
    text = normalize_answer(value)
    if not text or len(text) > 60:
        return None
    text = text.replace("π", "pi").replace("^", "**").replace("×", "*")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    text = re.sub(r"sqrt(\d+(?:\.\d+)?)", r"sqrt(\1)", text)
    text = re.sub(r"(\d|\))\s*(sqrt|pi|\()", r"\1*\2", text)
    text = re.sub(r"(pi)\s*(\d|sqrt|\()", r"\1*\2", text)
    try:
        tree = ast.parse(text, mode="eval")
        result = _evaluate_node(tree.body)
    except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError):
        return None
    if isinstance(result, complex) or not math.isfinite(result):
        return None
    return float(result)


def _evaluate_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id == "pi":
        return math.pi
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _BINARY_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        return _UNARY_OPERATORS[type(node.op)](_evaluate_node(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sqrt"
        and len(node.args) == 1
        and not node.keywords
    ):
        return math.sqrt(_evaluate_node(node.args[0]))
    raise ValueError("unsupported expression")
