# Golf Score Differential App

## What this project is
A web app that replaces a personal spreadsheet. A user enters their handicap
index plus a course's slope and rating, and the app shows the expected score
for that handicap on that course/tee — so a "bad" score on a hard course can
be seen for what it actually is: possibly a strong round.

Core formula (USGA / World Handicap System):
- Score Differential = (Score − Course Rating) × 113 / Slope Rating
- Expected Score = Handicap Index × (Slope / 113) + Course Rating

## Who's building this
The developer is an experienced Python/ML engineer (data science background)
who is NEW to full-stack web development and production architecture. This is
explicitly a learning project, not just a "ship it fast" project. Priorities,
in order:
1. Working, correct code
2. The developer actually understanding each new concept as it's introduced
3. Speed

When introducing a new concept for the first time (React state, REST routes,
ORMs, deployment config, etc.), briefly explain what it is and why it's needed
before or while writing it — don't just generate it silently. Prefer smaller,
understandable steps over large one-shot generations.

## Stack
- **Backend:** Python, FastAPI
- **Frontend:** React
- **Database:** Postgres (hosted — Supabase or Railway)
- **Deployment:** Frontend on Vercel, backend + DB on Railway or Render
- **Testing:** pytest for backend logic

## Build order (do not skip ahead)
1. Pure Python calculation functions (expected score, differential) + pytest
   unit tests against known-correct values. No web framework yet.
2. Wrap the functions in a FastAPI app with a couple of REST endpoints.
   Verify via FastAPI's auto-generated /docs page.
3. Minimal single-page React frontend: a form (handicap, slope, rating) that
   calls the API and displays the result.
4. Add Postgres: tables for courses (name, tee, slope, rating) and rounds
   (date, course, score, computed differential). Use SQLAlchemy as the ORM.
5. Deploy: backend + DB to Railway/Render, frontend to Vercel. Wire the
   frontend to the deployed backend URL via an environment variable.
6. (Stretch) Basic auth (e.g. Supabase Auth or Clerk) if/when other people
   will use it with their own data.
7. (Future) Automatic integration to pull slope and rating values for courses
   from their various tee boxes (e.g. from a golf course database API or
   web scraping).

## Conventions
- Keep the calculation logic backend-only and framework-free — it should be
  importable and testable without spinning up FastAPI.
- Prefer explicit, readable code over clever one-liners; this is a learning
  project.
- Update this file when a decision changes (e.g. swapping Railway for
  something else) so future sessions stay consistent.
