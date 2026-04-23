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

## Answer Keys

The catalog includes National Sprint, Target, and Team paper links for 2000-2017.
Auto-grading is enabled only for rounds that have imported answer keys. Use
`data/answer_keys.csv` as the import format. The first answer is shown on the
results page; extra accepted variants can be separated with `||`:

```csv
year,round,question_number,answer,points
2017,Sprint,1,5600 gallons||5600,1
```
