# Docker Local Run Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a one-command Docker workflow that initializes the SQLite database when needed and runs the MATHCOUNTS app locally with persistent scores.

**Architecture:** Move the "initialize database if needed, then run the server" flow into a testable package module so both local Python runs and Docker can reuse it. Build a minimal Docker image around the existing standard-library app, and use Docker Compose to expose the app on localhost while persisting the database on a host-mounted directory.

**Tech Stack:** Python 3 standard library, `unittest`, Docker, Docker Compose, SQLite

---

### Task 1: Add a failing bootstrap test

**Files:**
- Create: `tests/test_bootstrap.py`
- Modify: none
- Test: `tests/test_bootstrap.py`

**Step 1: Write the failing test**

Add tests that describe the bootstrap behavior:
- it initializes the database when the configured SQLite file does not exist
- it skips initialization when the file already exists
- it passes the configured host, port, and DB path to the server runner

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_bootstrap -v`

Expected: FAIL because the bootstrap module does not exist yet.

**Step 3: Write minimal implementation**

Create a small bootstrap module inside `mathcounts_platform` and wire enough behavior to satisfy the test.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_bootstrap -v`

Expected: PASS

### Task 2: Reuse bootstrap logic from scripts and Docker

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Modify: `scripts/init_db.py`
- Modify: `mathcounts_platform/bootstrap.py`
- Test: `tests/test_bootstrap.py`

**Step 1: Write the failing test**

Extend the bootstrap test coverage as needed for environment-driven config defaults used by Docker:
- local default port is `8000`
- Docker can override host and DB path through environment variables

**Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_bootstrap -v`

Expected: FAIL on the new assertions.

**Step 3: Write minimal implementation**

Implement config parsing in `mathcounts_platform/bootstrap.py`, keep `scripts/init_db.py` using the shared initialization logic, and add Docker files that invoke the bootstrap module.

**Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_bootstrap -v`

Expected: PASS

### Task 3: Document the local Docker flow

**Files:**
- Modify: `README.md`
- Test: manual README command review

**Step 1: Write the failing test**

No automated test required for documentation-only changes. Validate by ensuring the README includes exact commands for building and starting the Docker workflow.

**Step 2: Write minimal implementation**

Add a concise "Run with Docker" section with the `docker compose up --build` command, URL, and data persistence path.

**Step 3: Run verification**

Run:
- `python3 -m unittest -v`
- `docker compose config`
- `docker compose up --build -d`
- `curl -I http://127.0.0.1:8000/login`

Expected:
- tests pass
- compose file validates
- container starts
- the app responds on localhost
