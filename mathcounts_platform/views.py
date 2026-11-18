from html import escape
from urllib.parse import urlencode

from mathcounts_platform.rounds import (
    is_answer_key_complete,
    round_description,
    round_group_label,
    round_point_value,
    round_question_numbers,
)
from mathcounts_platform.topics import (
    DIFFICULTIES,
    ROUNDS,
    STATUSES,
    SUBJECTS,
    status_for,
)


def render_base(title, body, user=None, head_extra=""):
    account_html = ""
    if user:
        account_html = f"""
        <span class="account">{escape(user["email"])}</span>
        <form method="post" action="/logout" class="inline-form">
          <button type="submit">Log out</button>
        </form>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} - MATHCOUNTS National Practice</title>
  <link rel="stylesheet" href="/static/styles.css">
  {head_extra}
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/dashboard">MATHCOUNTS National Practice</a>
    <nav>
      <a href="/dashboard">Dashboard</a>
      <a href="/topics">Topics</a>
      <a href="/practice">Generated</a>
      <a href="/history">History</a>
      {account_html}
    </nav>
  </header>
  <main>
    {body}
  </main>
  <script src="/static/app.js"></script>
</body>
</html>"""


def render_login_page(error=None, message=None):
    error_html = _render_error(error)
    message_html = _render_notice(message)
    body = f"""
    <section class="auth-card">
      <h1>Log in</h1>
      {error_html}
      {message_html}
      <form method="post" action="/login">
        <label>Email <input type="email" name="email" required></label>
        <label>Password <input type="password" name="password" required></label>
        <button type="submit">Log in</button>
      </form>
      <p><a href="/forgot-password">Forgot password?</a></p>
      <p>New here? <a href="/register">Create an account</a>.</p>
    </section>
    """
    return render_base("Log in", body)


def render_forgot_password_page(message=None, reset_link=None):
    message_html = f'<p class="notice">{escape(message)}</p>' if message else ""
    reset_link_html = ""
    if reset_link:
        reset_link_html = f"""
        <div class="reset-link-box">
          <p>Development reset link:</p>
          <a href="{escape(reset_link)}">{escape(reset_link)}</a>
        </div>
        """
    body = f"""
    <section class="auth-card">
      <h1>Reset password</h1>
      <p>Enter your account email and we will create a one-time reset link.</p>
      {message_html}
      {reset_link_html}
      <form method="post" action="/forgot-password">
        <label>Email <input type="email" name="email" required></label>
        <button type="submit">Create reset link</button>
      </form>
      <p><a href="/login">Back to log in</a></p>
    </section>
    """
    return render_base("Forgot password", body)


def render_reset_password_page(token="", error=None):
    error_html = _render_error(error)
    body = f"""
    <section class="auth-card">
      <h1>Choose a new password</h1>
      {error_html}
      <form method="post" action="/reset-password">
        <input type="hidden" name="token" value="{escape(token)}">
        <label>New password <input type="password" name="password" required minlength="8"></label>
        <button type="submit">Reset password</button>
      </form>
      <p><a href="/login">Back to log in</a></p>
    </section>
    """
    return render_base("Reset password", body)


def render_register_page(error=None):
    error_html = _render_error(error)
    body = f"""
    <section class="auth-card">
      <h1>Create account</h1>
      {error_html}
      <form method="post" action="/register">
        <label>Email <input type="email" name="email" required></label>
        <label>Password <input type="password" name="password" required minlength="8"></label>
        <button type="submit">Create account</button>
      </form>
      <p>Already have an account? <a href="/login">Log in</a>.</p>
    </section>
    """
    return render_base("Create account", body)


def render_dashboard_page(user, years, attempts):
    year_cards = "\n".join(
        f"""
        <article class="year-card">
          <h2>{int(year["year"])}</h2>
          <div class="round-links">
            <a href="/test?year={int(year["year"])}&round=Sprint">Sprint</a>
            <a href="/test?year={int(year["year"])}&round=Target">Target</a>
            <a href="/test?year={int(year["year"])}&round=Team">Team</a>
          </div>
        </article>
        """
        for year in years
    )
    recent = _render_attempt_list(attempts[:5]) if attempts else "<p>No attempts yet.</p>"
    body = f"""
    <section class="hero">
      <p class="eyebrow">National archive</p>
      <h1>Choose a year and take a round.</h1>
      <p>Practice Sprint, Target, and Team rounds directly in the platform. Your scores save to your account.</p>
    </section>
    <section class="topic-callout">
      <div>
        <h2>Practice by topic</h2>
        <p>Browse problems grouped by subject (Algebra, Geometry, Number Theory, Counting &amp; Probability, General Math) and difficulty.</p>
      </div>
      <a class="button" href="/topics">Browse topics</a>
    </section>
    <section>
      <h2>Years</h2>
      <div class="year-grid">{year_cards}</div>
    </section>
    <section>
      <h2>Recent attempts</h2>
      {recent}
    </section>
    """
    return render_base("Dashboard", body, user=user)


def render_test_page(user, year, round_name, resource, answer_keys, reference_links):
    paper_url = resource["url"]
    iframe_url = _embed_url(paper_url)
    reference_html = _render_reference_links(reference_links)
    question_numbers = round_question_numbers(round_name, answer_keys)
    complete_answer_key = is_answer_key_complete(round_name, answer_keys)
    description = round_description(round_name)
    description_html = f'<p class="round-description">{escape(description)}</p>' if description else ""
    if question_numbers:
        answer_inputs = _render_answer_inputs(round_name, question_numbers, disabled=not complete_answer_key)
        submit_html = (
            '<button type="submit">Submit answers</button>'
            if complete_answer_key
            else '<p class="warning">Import a complete answer key before this round can be scored.</p>'
        )
        answer_form = f"""
        <form method="post" action="/submit-attempt" class="answer-sheet">
          <input type="hidden" name="year" value="{int(year)}">
          <input type="hidden" name="round" value="{escape(round_name)}">
          <div class="answer-grid">{answer_inputs}</div>
          {submit_html}
        </form>
        """
    else:
        answer_form = """
        <div class="empty-state">
          <h2>Answer key needed</h2>
          <p>This round is in the catalog, but auto-grading is disabled until its answer key is imported.</p>
        </div>
        """

    body = f"""
    <section class="test-heading">
      <p class="eyebrow">{int(year)} National</p>
      <h1>{escape(round_name)} Round</h1>
      <a class="button secondary" href="{escape(paper_url)}" target="_blank" rel="noreferrer">Open paper in new tab</a>
    </section>
    <section class="test-layout">
      <div class="paper-panel">
        <iframe title="{int(year)} {escape(round_name)} paper" src="{escape(iframe_url)}"></iframe>
      </div>
      <aside class="answer-panel">
        <h2>Your answers</h2>
        {description_html}
        {answer_form}
        {reference_html}
      </aside>
    </section>
    """
    return render_base(f"{year} {round_name}", body, user=user)


def render_results_page(user, attempt, per_question_results, problem_tags=None):
    body = f"""
    <section class="result-card">
      <h1>Score: {int(attempt["score"])} / {int(attempt["max_score"])}</h1>
      {_render_result_rows(per_question_results, problem_tags or {})}
    </section>
    """
    return render_base("Results", body, user=user)


def render_history_page(user, attempts):
    body = f"""
    <section>
      <h1>Attempt history</h1>
      {_render_attempt_list(attempts) if attempts else "<p>No attempts yet.</p>"}
    </section>
    """
    return render_base("History", body, user=user)


def _render_error(error):
    if not error:
        return ""
    return f'<p class="error">{escape(error)}</p>'


def _render_notice(message):
    if not message:
        return ""
    return f'<p class="notice">{escape(message)}</p>'


def _embed_url(url):
    if "drive.google.com/open?id=" in url:
        file_id = url.split("open?id=", 1)[1].split("&", 1)[0]
        return f"https://drive.google.com/file/d/{file_id}/preview"
    if url.startswith("/past_paper/"):
        if "#" in url:
            return f"{url}&zoom=page-width"
        return f"{url}#zoom=page-width"
    return url


def _render_reference_links(reference_links):
    if not reference_links:
        return ""
    items = "\n".join(
        f'<li><a href="{escape(link["url"])}" target="_blank" rel="noreferrer">{escape(link["label"])}</a></li>'
        for link in reference_links
    )
    return f"""
    <section class="references">
      <h2>Reference links</h2>
      <ul>{items}</ul>
    </section>
    """


def _render_answer_inputs(round_name, question_numbers, disabled=False):
    disabled_attr = " disabled" if disabled else ""
    chunks = []
    previous_group = ""
    for question_number in question_numbers:
        group_label = round_group_label(round_name, question_number)
        if group_label and group_label != previous_group:
            chunks.append(f'<h3 class="pair-label">{escape(group_label)}</h3>')
            previous_group = group_label
        point_value = round_point_value(round_name, question_number)
        chunks.append(
            f"""
            <label class="answer-row">
              <span>#{int(question_number)}</span>
              <input name="answer_{int(question_number)}" autocomplete="off"{disabled_attr}>
              <small>{point_value} pt</small>
            </label>
            """
        )
    return "\n".join(chunks)


def _render_attempt_list(attempts):
    items = "\n".join(
        f"""
        <li>
          <strong>{int(attempt["year"])} {escape(attempt["round"])}</strong>
          <span>{int(attempt["score"])} / {int(attempt["max_score"])}</span>
          <span>{escape(str(attempt["submitted_at"]))}</span>
        </li>
        """
        for attempt in attempts
    )
    return f'<ul class="attempt-list">{items}</ul>'


def _render_result_rows(results, problem_tags):
    topic_header = "<th>Topic</th>" if problem_tags else ""
    rows = "\n".join(
        f"""
        <tr class="{'correct' if result["is_correct"] else 'incorrect'}">
          <td>{int(result["question_number"])}</td>
          {_render_topic_cell(problem_tags.get(int(result["question_number"]))) if problem_tags else ""}
          <td>{escape(str(result["submitted_answer"]))}</td>
          <td>{escape(str(result["correct_answer"]))}</td>
          <td>{int(result["points"])}</td>
          <td>{'Correct' if result["is_correct"] else 'Incorrect'}</td>
        </tr>
        """
        for result in results
    )
    return f"""
    <table class="results-table">
      <thead>
        <tr><th>#</th>{topic_header}<th>Your answer</th><th>Correct answer</th><th>Points</th><th>Result</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _render_topic_cell(problem):
    if not problem:
        return "<td></td>"
    return f'<td class="topic-cell">{escape(problem["subject"])} · {escape(problem["difficulty"])}</td>'


def render_topics_page(user, problems, grouped, summary, filters, statuses):
    has_filters = bool(filters)
    if grouped:
        groups_html = "\n".join(
            _render_subject_group(subject, by_difficulty, filters, statuses, open_by_default=has_filters)
            for subject, by_difficulty in grouped.items()
        )
    else:
        groups_html = '<p class="empty-note">No problems match these filters.</p>'
    clear_link = '<a href="/topics">Clear filters</a>' if has_filters else ""
    body = f"""
    <section class="hero">
      <p class="eyebrow">Practice by topic</p>
      <h1>Problems grouped by subject and difficulty.</h1>
      <p>Difficulty is estimated from where each problem sits in its round, since MATHCOUNTS orders problems roughly from easiest to hardest.</p>
    </section>
    <section>
      <h2>Overview</h2>
      {_render_subject_summary(summary)}
    </section>
    <section>
      <form method="get" action="/topics" class="topic-filters">
        {_render_select("subject", "Subject", SUBJECTS, filters)}
        {_render_select("difficulty", "Difficulty", DIFFICULTIES, filters)}
        {_render_select("round", "Round", ROUNDS, filters)}
        {_render_select("status", "Status", tuple(STATUSES), filters, labels=STATUSES)}
        <button type="submit">Filter</button>
        {clear_link}
      </form>
      <p class="match-count">{len(problems)} problem{"s" if len(problems) != 1 else ""}</p>
      {_render_topic_generate_form(filters)}
      {groups_html}
    </section>
    """
    return render_base("Topics", body, user=user)


def render_problem_page(
    user,
    problem,
    paper_url,
    filters,
    status,
    answer_key_available,
    check=None,
    correct_answer=None,
    previous_problem=None,
    next_problem=None,
):
    title = f'{int(problem["year"])} {problem["round"]} #{int(problem["question_number"])}'
    if check is not None:
        if check["is_correct"]:
            check_html = f"""
            <div class="check-result correct">
              <strong>Correct!</strong>
              <p>Official answer: {escape(str(correct_answer))}</p>
            </div>
            """
        else:
            check_html = f"""
            <div class="check-result incorrect">
              <strong>Not quite.</strong>
              <p>You answered: {escape(str(check["submitted_answer"])) or "(blank)"}</p>
              <p>Official answer: {escape(str(correct_answer))}</p>
            </div>
            """
    else:
        check_html = ""

    if answer_key_available:
        filter_inputs = "".join(
            f'<input type="hidden" name="{escape(name)}" value="{escape(value)}">'
            for name, value in filters.items()
        )
        answer_form = f"""
        <form method="post" action="/check-problem" class="single-answer">
          <input type="hidden" name="year" value="{int(problem["year"])}">
          <input type="hidden" name="round" value="{escape(problem["round"])}">
          <input type="hidden" name="q" value="{int(problem["question_number"])}">
          {filter_inputs}
          <label class="answer-row">
            <span>Your answer</span>
            <input name="answer" autocomplete="off" autofocus>
          </label>
          <button type="submit">Check answer</button>
        </form>
        """
    else:
        answer_form = '<p class="warning">No answer key is imported for this problem yet.</p>'

    nav_links = []
    if previous_problem:
        nav_links.append(f'<a href="{escape(_problem_href(previous_problem, filters))}">&larr; Previous</a>')
    if next_problem:
        nav_links.append(f'<a href="{escape(_problem_href(next_problem, filters))}">Next &rarr;</a>')
    nav_html = f'<div class="problem-nav">{"".join(nav_links)}</div>' if nav_links else ""
    back_href = "/topics" + (f"?{urlencode(filters)}" if filters else "")
    round_href = f'/test?{urlencode({"year": int(problem["year"]), "round": problem["round"]})}'
    summary_html = f'<p class="problem-summary">{escape(problem["summary"])}</p>' if problem["summary"] else ""

    body = f"""
    <section class="test-heading">
      <div>
        <p class="eyebrow">{escape(problem["subject"])} · {escape(problem["difficulty"])}</p>
        <h1>{escape(title)}</h1>
        {summary_html}
      </div>
      <a class="button secondary" href="{escape(paper_url)}" target="_blank" rel="noreferrer">Open paper in new tab</a>
    </section>
    <section class="test-layout">
      <div class="paper-panel">
        <iframe title="{escape(title)}" src="{escape(_embed_url(paper_url))}"></iframe>
      </div>
      <aside class="answer-panel">
        <h2>Problem {int(problem["question_number"])}</h2>
        <p>{_render_status_badge(status)}</p>
        {check_html}
        {answer_form}
        <form method="post" action="/generate-problem" class="generate-form">
          <input type="hidden" name="year" value="{int(problem["year"])}">
          <input type="hidden" name="round" value="{escape(problem["round"])}">
          <input type="hidden" name="q" value="{int(problem["question_number"])}">
          <button type="submit" class="secondary">Generate a similar problem</button>
          <small>New {escape(problem["subject"])} problem at {escape(problem["difficulty"])} difficulty</small>
        </form>
        {nav_html}
        <p><a href="{escape(back_href)}">Back to topics</a> · <a href="{escape(round_href)}">Take the full round</a></p>
      </aside>
    </section>
    """
    return render_base(title, body, user=user)


def _problem_href(problem, filters):
    params = {
        "year": int(problem["year"]),
        "round": problem["round"],
        "q": int(problem["question_number"]),
    }
    params.update(filters)
    return f"/problem?{urlencode(params)}"


def _render_select(name, label, options, filters, labels=None):
    labels = labels or {}
    current = filters.get(name, "")
    option_html = "".join(
        f'<option value="{escape(option)}"{" selected" if option == current else ""}>{escape(labels.get(option, option))}</option>'
        for option in options
    )
    return f"""
    <label>{escape(label)}
      <select name="{escape(name)}">
        <option value="">All</option>
        {option_html}
      </select>
    </label>
    """


def _render_subject_summary(summary):
    rows = []
    for item in summary:
        cells = "".join(
            f'<td><a href="/topics?{escape(urlencode({"subject": item["subject"], "difficulty": difficulty}))}">'
            f'{int(item["by_difficulty"][difficulty])}</a></td>'
            for difficulty in DIFFICULTIES
        )
        progress = f'{int(item["solved"])} / {int(item["tried"])}' if item["tried"] else "&mdash;"
        rows.append(
            f"""
            <tr>
              <th scope="row"><a href="/topics?{escape(urlencode({"subject": item["subject"]}))}">{escape(item["subject"])}</a></th>
              {cells}
              <td>{int(item["total"])}</td>
              <td>{progress}</td>
            </tr>
            """
        )
    headers = "".join(f"<th>{escape(d)}</th>" for d in DIFFICULTIES)
    return f"""
    <table class="results-table topic-summary">
      <thead><tr><th>Subject</th>{headers}<th>Total</th><th>Solved / tried</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    """


def _render_subject_group(subject, by_difficulty, filters, statuses, open_by_default):
    count = sum(len(items) for items in by_difficulty.values())
    difficulty_html = "\n".join(
        f"""
        <h3>{escape(difficulty)} <small>({len(items)})</small></h3>
        <ul class="problem-list">
          {"".join(_render_problem_item(problem, filters, statuses) for problem in items)}
        </ul>
        """
        for difficulty, items in by_difficulty.items()
    )
    open_attr = " open" if open_by_default else ""
    return f"""
    <details class="subject-group"{open_attr}>
      <summary><h2>{escape(subject)} <small>({count})</small></h2></summary>
      {difficulty_html}
    </details>
    """


def _render_problem_item(problem, filters, statuses):
    status = status_for(problem, statuses)
    summary = escape(problem["summary"]) if problem["summary"] else ""
    return f"""
    <li>
      <a href="{escape(_problem_href(problem, filters))}">
        <strong>{int(problem["year"])} {escape(problem["round"])} #{int(problem["question_number"])}</strong>
        <span>{summary}</span>
      </a>
      {_render_status_badge(status)}
    </li>
    """


_EXTRA_STATUS_LABELS = {"pending": "Generating", "failed": "Failed"}


def _render_status_badge(status):
    label = STATUSES.get(status) or _EXTRA_STATUS_LABELS.get(status, status)
    return f'<span class="status-badge status-{escape(status)}">{escape(label)}</span>'


def _render_topic_generate_form(filters):
    subject = filters.get("subject")
    difficulty = filters.get("difficulty")
    if subject and difficulty:
        label = f"{subject} · {difficulty}"
    elif subject or difficulty:
        label = subject or f"{difficulty} (any subject)"
    else:
        label = "any subject and difficulty"
    hidden = "".join(
        f'<input type="hidden" name="{name}" value="{escape(filters[name])}">'
        for name in ("subject", "difficulty", "round")
        if name in filters
    )
    return f"""
    <form method="post" action="/generate-problem" class="generate-form topic-generate">
      {hidden}
      <button type="submit" class="secondary">Generate a new problem</button>
      <small>Creates a fresh problem like a random one from: {escape(label)}</small>
    </form>
    """


def render_practice_page(user, generated, source=None):
    if generated["status"] == "pending":
        return _render_pending_practice_page(user, generated)
    if generated["status"] == "failed":
        return _render_failed_practice_page(user, generated)
    subject = generated["subject"]
    difficulty = generated["difficulty"]
    unit = generated["unit"] or ""
    answer_display = f'{generated["answer"]} {unit}'.strip()
    source_label = (
        f'{int(generated["source_year"])} {generated["source_round"]} #{int(generated["source_question_number"])}'
    )
    source_href = "/problem?" + urlencode(
        {
            "year": int(generated["source_year"]),
            "round": generated["source_round"],
            "q": int(generated["source_question_number"]),
        }
    )
    source_summary = f' &mdash; {escape(source["summary"])}' if source and source.get("summary") else ""

    if generated["is_correct"] is None:
        check_html = ""
        status = "new"
    elif generated["is_correct"]:
        status = "solved"
        check_html = f"""
        <div class="check-result correct">
          <strong>Correct!</strong>
          <p>Answer: {escape(answer_display)}</p>
        </div>
        """
    else:
        status = "missed"
        check_html = f"""
        <div class="check-result incorrect">
          <strong>Not quite.</strong>
          <p>You answered: {escape(str(generated["submitted_answer"])) or "(blank)"}</p>
          <p>Answer: {escape(answer_display)}</p>
        </div>
        """
    solution_open = " open" if generated["is_correct"] is not None else ""
    solution_html = (
        f"""
        <details class="solution"{solution_open}>
          <summary>{"Solution" if generated["is_correct"] is not None else "Show answer and solution"}</summary>
          <p><strong>Answer:</strong> {escape(answer_display)}</p>
          <div class="solution-text">{escape(generated["solution"])}</div>
        </details>
        """
        if generated["solution"]
        else ""
    )
    unit_hint = f"<small>Unit: {escape(unit)} (optional)</small>" if unit else ""

    body = f"""
    <section class="test-heading">
      <div>
        <p class="eyebrow">{escape(subject)} · {escape(difficulty)} · AI-generated</p>
        <h1>Practice problem</h1>
        <p class="problem-summary">Modeled on <a href="{escape(source_href)}">{escape(source_label)}</a>{source_summary}</p>
      </div>
      {_render_status_badge(status)}
    </section>
    <section class="practice-layout">
      <article class="generated-problem">
        <div class="problem-text">{escape(generated["problem_text"])}</div>
        <p class="generated-note">Generated by AI and checked by solving it a second time independently. If something looks off, generate another.</p>
      </article>
      <aside class="answer-panel">
        {check_html}
        <form method="post" action="/check-practice" class="single-answer">
          <input type="hidden" name="id" value="{int(generated["id"])}">
          <label class="answer-row">
            <span>Your answer</span>
            <input name="answer" autocomplete="off" autofocus>
            {unit_hint}
          </label>
          <button type="submit">Check answer</button>
        </form>
        {solution_html}
        {_render_generate_again_form(generated, "Generate another like this")}
        <p><a href="/practice">All generated problems</a> · <a href="/topics">Topics</a></p>
      </aside>
    </section>
    """
    return render_base("Practice problem", body, user=user)


def render_generated_list_page(user, generated_problems):
    if generated_problems:
        items = "\n".join(
            f"""
            <li>
              <a href="/practice?id={int(item["id"])}">
                <strong>{escape(item["subject"])} · {escape(item["difficulty"])}</strong>
                <span>{escape(_truncate(item["problem_text"] or _pending_text(item), 110))}</span>
              </a>
              {_render_status_badge(_generated_status(item))}
            </li>
            """
            for item in generated_problems
        )
        content = f'<ul class="problem-list">{items}</ul>'
    else:
        content = (
            '<p class="empty-note">No generated problems yet. Open any problem from '
            '<a href="/topics">Topics</a> and choose &ldquo;Generate a similar problem&rdquo;.</p>'
        )
    body = f"""
    <section>
      <p class="eyebrow">AI practice</p>
      <h1>Generated problems</h1>
      <p>New problems created to match the subject and difficulty of real National problems.</p>
      {content}
    </section>
    """
    return render_base("Generated problems", body, user=user)


def render_generation_error_page(user, message, back_href="/topics"):
    body = f"""
    <section class="auth-card">
      <h1>Couldn&rsquo;t generate a problem</h1>
      <p class="error">{escape(message)}</p>
      <p><a href="{escape(back_href)}">Go back</a></p>
    </section>
    """
    return render_base("Generation failed", body, user=user)


def _generated_status(item):
    if item["status"] in ("pending", "failed"):
        return item["status"]
    if item["is_correct"] is None:
        return "new"
    return "solved" if item["is_correct"] else "missed"


def _render_generate_again_form(generated, label):
    return f"""
    <form method="post" action="/generate-problem" class="generate-form">
      <input type="hidden" name="year" value="{int(generated["source_year"])}">
      <input type="hidden" name="round" value="{escape(generated["source_round"])}">
      <input type="hidden" name="q" value="{int(generated["source_question_number"])}">
      <button type="submit" class="secondary">{escape(label)}</button>
    </form>
    """


def _render_pending_practice_page(user, generated):
    body = f"""
    <section class="auth-card generating">
      <p class="eyebrow">{escape(generated["subject"])} · {escape(generated["difficulty"])}</p>
      <h1>Generating your problem…</h1>
      <div class="spinner" aria-hidden="true"></div>
      <p>DeepSeek is writing a new problem and then solving it again independently to check the answer.
      This usually takes under a minute; harder problems can take a few minutes.</p>
      <p class="match-count">This page refreshes automatically.</p>
      <p><a href="/practice">All generated problems</a></p>
    </section>
    """
    return render_base(
        "Generating problem",
        body,
        user=user,
        head_extra='<meta http-equiv="refresh" content="4">',
    )


def _render_failed_practice_page(user, generated):
    body = f"""
    <section class="auth-card">
      <p class="eyebrow">{escape(generated["subject"])} · {escape(generated["difficulty"])}</p>
      <h1>Couldn&rsquo;t generate this problem</h1>
      <p class="error">{escape(generated["error"] or "Generation failed.")}</p>
      {_render_generate_again_form(generated, "Try again")}
      <p><a href="/practice">All generated problems</a> · <a href="/topics">Topics</a></p>
    </section>
    """
    return render_base("Generation failed", body, user=user)


def _pending_text(item):
    if item["status"] == "pending":
        return "Generating…"
    return item["error"] or "Generation failed"


def _truncate(text, limit):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
