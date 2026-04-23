# Password Reset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a secure forgot-password flow that lets a user set a new password without exposing the old password.

**Architecture:** Store one-time password reset tokens as hashes in SQLite with expiration and used timestamps. The local MVP shows the reset link on-screen after the user submits their email; a production email sender can replace that presentation later without changing the token model.

**Tech Stack:** Python standard library, SQLite, `unittest`, server-rendered HTML.

---

### Task 1: Token Storage

**Files:**
- Modify: `mathcounts_platform/db.py`
- Modify: `mathcounts_platform/auth.py`
- Test: `tests/test_auth.py`

**Steps:**
1. Write failing tests for creating a reset token, looking it up, marking it used, and updating a password hash.
2. Add a `password_reset_tokens` table to migration.
3. Add helper functions for token creation, token lookup, token usage, and user password update.
4. Run `python3 -m unittest -v tests.test_auth`.

### Task 2: Pages And Routes

**Files:**
- Modify: `mathcounts_platform/views.py`
- Modify: `mathcounts_platform/server.py`
- Test: `tests/test_views.py`

**Steps:**
1. Write failing tests for the forgot-password and reset-password pages.
2. Add `/forgot-password` and `/reset-password` GET/POST routes.
3. Link the login page to forgot password.
4. On successful reset, redirect to login with a message.

### Task 3: Verification And Publish

**Files:**
- Verify all touched files.

**Steps:**
1. Run `python3 -m unittest -v`.
2. Restart the local server.
3. Verify the reset flow with `curl`.
4. Commit with `feat: add password reset flow`.
5. Push `main`.
