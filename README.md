# MATHCOUNTS National Practice

A dependency-light Python web platform for practicing MATHCOUNTS National
rounds, grading structured answer submissions, and storing attempt history.
The catalog includes remote archive links for 2000-2017 and local PDFs for
2018, 2019, 2021, 2022, 2023, 2024, and 2025.

## Setup

This project uses only the Python standard library for the MVP.

```bash
python3 --version
```

## Run Tests

```bash
python3 -m unittest -v
```

## Initialize Database

```bash
python3 scripts/init_db.py --answer-keys data/answer_keys.csv
```

## Run App

```bash
python3 -m mathcounts_platform.server --host 127.0.0.1 --port 8000 --db data/app.sqlite3
```

Then open `http://127.0.0.1:8000`.

## Run with Docker

Build and start the local Docker version with:

```bash
docker compose up --build
```

Then open `http://127.0.0.1:8000`.

Scores persist in `docker-data/app.sqlite3` on your machine, so container
restarts do not wipe attempt history.

To stop the Docker app:

```bash
docker compose down
```

## Practice by Topic

The **Topics** page (`/topics`) groups individual problems by subject and
difficulty, and you can filter by subject, difficulty, round, and status
(not tried / missed / solved). Each problem opens on its own page with the
paper scrolled to that problem and a single answer box. Single-problem checks
are saved and combine with full-round attempts. Your latest answer to a problem
sets its status.

Tags live in `data/problem_tags.csv` and are loaded when the server reads them
(no database re-init needed):

```csv
year,round,question_number,subject,difficulty,page,summary
2025,Sprint,1,Algebra,Easy,11,Greatest of three consecutive even integers summing to 66
```

- `subject` is one of: Algebra, Geometry, Number Theory, Counting & Probability, General Math.
- `difficulty` is Easy, Medium, or Hard. Leave it blank to estimate it from the
  problem's position in its round (Sprint 1-10 / 11-20 / 21-30, Target 1-2 / 3-6 / 7-8,
  Team 1-3 / 4-7 / 8-10).
- `page` is the PDF page the problem appears on.

Only years with local PDFs (2018-2025) are tagged. Edit the CSV to correct or
add tags.

## AI-Generated Practice Problems

Every problem page has a **Generate a similar problem** button. The Topics page
has **Generate a new problem**, which works from a random problem that matches
the current subject and difficulty filters. Each one creates a new problem on the
same subject, at the same difficulty, and testing the same core idea, using the
[DeepSeek API](https://api-docs.deepseek.com/) or any OpenAI-compatible
DeepSeek endpoint.

Generation runs in the background. The button opens a "Generating…" page that
refreshes until the problem is ready, which usually takes 10-60 seconds and can
take a few minutes for Hard problems. A second, independent DeepSeek call then
solves and reviews each draft. A draft is kept only if:

- both answers agree,
- the reviewer finds it well-posed (nothing contradictory or ambiguous, and no
  figure needed), and
- it isn't rated two levels easier than requested.

Rejected drafts are retried up to 3 times, within about 5 minutes. The reviewer's
own worked solution is the one shown to students. Generated problems are saved
per user under **Generated** (`/practice`).

Configure it in a `.env` file in the project root. The file is gitignored and
excluded from Docker images, and real environment variables override it. Restart
the app after editing it.

```bash
# Official DeepSeek API
DEEPSEEK_API_KEY=sk-...

# Or a self-hosted, OpenAI-compatible endpoint, e.g. DeepSeek v4.1 Flash
# through a local LiteLLM proxy (no real key needed if the proxy has none):
DEEPSEEK_BASE_URL=http://127.0.0.1:4000/v1
DEEPSEEK_MODEL=deepseek-v4.1-flash
DEEPSEEK_API_KEY=litellm-local
DEEPSEEK_GENERATE_THINKING=off   # vLLM only: skip hidden reasoning when drafting

# Optional
# DEEPSEEK_MAX_TOKENS=8000
```

Docker Compose passes `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` from the same
`.env` into the container. For a proxy running on the host, add
`DEEPSEEK_BASE_URL` and `DEEPSEEK_GENERATE_THINKING` to `docker-compose.yml` and
use `http://host.docker.internal:4000/v1`, because inside the container
`127.0.0.1` refers to the container itself.

## Answer Keys

The catalog includes National Sprint, Target, and Team paper links for 2000-2017.
Auto-grading is enabled only for rounds that have imported answer keys. Use
`data/answer_keys.csv` as the import format. The first answer is shown on the
results page; extra accepted variants can be separated with `||`:

```csv
year,round,question_number,answer,points
2017,Sprint,1,5600 gallons||5600,1
```
