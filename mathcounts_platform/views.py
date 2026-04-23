from html import escape

from mathcounts_platform.rounds import (
    is_answer_key_complete,
    round_description,
    round_group_label,
    round_point_value,
    round_question_numbers,
)


def render_base(title, body, user=None):
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
</head>
<body>
  <header class="site-header">
    <a class="brand" href="/dashboard">MATHCOUNTS National Practice</a>
    <nav>
      <a href="/dashboard">Dashboard</a>
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


def render_login_page(error=None):
    error_html = _render_error(error)
    body = f"""
    <section class="auth-card">
      <h1>Log in</h1>
      {error_html}
      <form method="post" action="/login">
        <label>Email <input type="email" name="email" required></label>
        <label>Password <input type="password" name="password" required></label>
        <button type="submit">Log in</button>
      </form>
      <p>New here? <a href="/register">Create an account</a>.</p>
    </section>
    """
    return render_base("Log in", body)


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


def render_results_page(user, attempt, per_question_results):
    body = f"""
    <section class="result-card">
      <h1>Score: {int(attempt["score"])} / {int(attempt["max_score"])}</h1>
      {_render_result_rows(per_question_results)}
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


def _embed_url(url):
    if "drive.google.com/open?id=" in url:
        file_id = url.split("open?id=", 1)[1].split("&", 1)[0]
        return f"https://drive.google.com/file/d/{file_id}/preview"
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


def _render_result_rows(results):
    rows = "\n".join(
        f"""
        <tr class="{'correct' if result["is_correct"] else 'incorrect'}">
          <td>{int(result["question_number"])}</td>
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
        <tr><th>#</th><th>Your answer</th><th>Correct answer</th><th>Points</th><th>Result</th></tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """
