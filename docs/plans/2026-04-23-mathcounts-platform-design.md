# MATHCOUNTS National Practice Platform Design

## Goal

Build a web platform where users can practice MATHCOUNTS National competition rounds by year, answer questions directly inside the platform, receive automatic grading, and keep score history across devices.

## Source Material

The initial catalog comes from `https://mathteamnyc.weebly.com/mathcounts.html`, which lists MATHCOUNTS National materials for 2000 through 2017.

The platform will use source links for the original papers and reference documents instead of storing downloaded PDFs in the project. This keeps the project lightweight and preserves the original materials.

## Users And Persistence

The platform will support user accounts and login. Each saved attempt belongs to a user so scores and history persist across devices.

## Test Catalog

The database will store a structured catalog of years and resources.

Each year can include:

- Auto-graded practice rounds: Sprint, Target, Team.
- Reference resources: Answers, Solutions, Results, CDR, Masters, Competitors, Highlights, or other links when present.

## Test-Taking Flow

1. A user logs in.
2. The user selects a National competition year.
3. The user selects Sprint, Target, or Team.
4. The platform displays the original paper inside the test-taking page where possible.
5. The platform renders answer fields for that round.
6. The user enters answers directly in the platform.
7. The user submits the attempt.
8. The backend grades the attempt against the stored answer key.
9. The platform shows the score, correct/incorrect results, and saves the attempt.

## Grading

The backend will compare normalized user responses against stored answer-key entries. Normalization should handle common answer formatting differences such as whitespace and case. More advanced equivalence, such as fractions and decimals, can be added after the basic platform is working.

Each saved attempt should include:

- User ID.
- Year.
- Round.
- Submitted answers.
- Per-question correctness.
- Score.
- Timestamp.

## Data Requirements

The app needs structured answer keys for Sprint, Target, and Team rounds. The system should be built so answer keys can be seeded or imported cleanly. If an answer key has not yet been entered for a round, the UI should show the paper and reference links but disable auto-graded submission for that round.

## Recommended Architecture

Use a full-stack web app with:

- A frontend dashboard for year and round selection.
- A test-taking interface with embedded paper/source link plus answer inputs.
- Backend routes or actions for authentication, catalog retrieval, attempt submission, and score history.
- A relational database for users, paper metadata, answer keys, attempts, and responses.

## MVP Scope

The MVP should provide:

- Login/account support.
- National years 2000-2017 in the catalog.
- Sprint, Target, and Team selectable as auto-graded rounds.
- Source links for all listed National resources.
- Answer input forms generated from round metadata.
- Backend grading and persisted attempt history.
- Clear handling for rounds whose answer keys are not yet available.

## Out Of Scope For MVP

- Manual transcription of every question into native app content.
- Downloading and storing all PDF files locally.
- Advanced mathematical answer equivalence beyond basic normalization.
- Teacher/classroom administration.
- Timers, leaderboards, and analytics dashboards.
