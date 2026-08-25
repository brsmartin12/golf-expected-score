# Golf Score Differential App

## What this project is
A web app that replaces a personal spreadsheet. A user enters their handicap
index plus a course's slope and rating, and the app shows the expected score
for that handicap on that course/tee — so a "bad" score on a hard course can
be seen for what it actually is: possibly a strong round.

Core formula (USGA / World Handicap System):
- Score Differential = (Score − Course Rating) × 113 / Slope Rating
- Expected Score = Handicap Index × (Slope / 113) + Course Rating

**But the calculator is not the product.** The USGA already ships that. The
product is what you can only say once rounds accumulate: a Handicap Index is the
average of your *best 8 of the last 20* differentials, which makes it a measure
of **potential**, not expectation — the round you shoot when you play well. Your
*typical* round runs about 3 strokes worse. The app's job is to show both, to
estimate how you are playing **right now** (the official index is a deliberately
slow, trailing number), and to surface consistency and course fit, which the
index throws away entirely.

**See `ROADMAP.md`** for the full vision and the feature tiers. Read it before
proposing product direction — the "why" lives there, this file is the "how."

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

## Scope decisions (settled — don't relitigate without a reason)
- **Score-only entry.** A round is date + course + tee + total score. No
  hole-by-hole, no fairways/GIR/putts. Data-entry friction is what kills golf
  apps; a round must stay a 15-second entry.
- **Multi-user from the schema up.** This is for the developer *and golf
  friends*, so `user_id` exists from the first table, even before auth ships.
- **Headline feature is the current-form index** (step 7 below). Earlier steps
  exist to make it possible.

## Build order (do not skip ahead)
1. Pure Python calculation functions (expected score, differential) + pytest
   unit tests against known-correct values. No web framework yet. **Done.**
2. Wrap the functions in a FastAPI app with a couple of REST endpoints.
   Verify via FastAPI's auto-generated /docs page. **Done.**
3. Minimal single-page React frontend: a form (handicap, slope, rating) that
   calls the API and displays the result. **Done** — but this screen is
   *scaffolding*, not the product: it is the calculator `ROADMAP.md` opens by
   saying should not exist twice. Don't polish it. See Tier 0 in `ROADMAP.md`
   for what survives from it (`api.js`, the env wiring, the to-par convention)
   and what gets replaced (the form, once courses and tees are pickable).
4. Add Postgres with SQLAlchemy as the ORM. Tables: `users`, `courses`, `tees`,
   `rounds`, `handicap_snapshots` — see the schema in `ROADMAP.md`. Two things
   are much cheaper now than later:
   - `tees` is its own table, not a column on `courses`. Slope and rating are
     per-tee.
   - Each round records the handicap index *in effect when it was played*, but
     the column is nullable: it is derivable from the surrounding rounds (best 8
     of the trailing 20), which is what makes hand-backfilling possible. Never
     recompute history against *today's* index — that silently rewrites every
     past round and destroys every trend.
5. **Backfill the ~30 rounds of history**, deliberately this early: with no
   backfill the app has zero rounds and can say nothing interesting for a full
   season. This is what makes steps 6–8 useful on day one. The history is in
   18Birdies, which has no export, so this is hand entry — meaning the work is
   *quick-add entry UX*, not a CSV parser. Do import the existing spreadsheet,
   but as seed data for `courses` and `tees`; it is a calculator, not a record
   of scores.
6. Score-only analytics, as pure functions in `backend/golf/` (test-first, same
   as step 1): full WHS index calculation (best 8 of 20, safeguards included),
   index projection ("shoot 84 and you go 12.4 → 12.1"), round percentile,
   typical-vs-potential, cross-course score translation, pre-round target card.
7. **Current-form index** — the headline. Recency-weighted estimate of mean and
   spread over your differentials, presented against the official index
   ("official 12.4, playing like a 10.8"), plus consistency as a first-class
   stat and trends reported with honest error bars.
8. Course fit, done honestly: per-course and per-tee strokes-vs-expected,
   shrunk toward zero with confidence intervals, so "this course suits your
   game" is only claimed when the data supports it — and says "need 4 more
   rounds here" when it doesn't.
9. Deploy: backend + DB to Railway/Render, frontend to Vercel. Wire the
   frontend to the deployed backend URL via an environment variable.
10. Auth (Supabase Auth or Clerk) + groups, so friends can use it with their
    own data. Then the group leaderboard ranked by *strokes vs. expected*
    rather than raw score, and a net match calculator (the math for which is
    already in `handicap.py`).
11. (Future) Automatic integration to pull slope and rating values for courses
    from their various tee boxes; real PCC from historical weather.

## Project layout
```
ROADMAP.md            product vision and feature tiers — the "why"
backend/
  pyproject.toml      package metadata; `pip install -e ".[dev]"` to set up
  golf/handicap.py    all calculation logic (framework-free, no I/O)
  api/main.py         FastAPI routes; api/schemas.py holds the Pydantic models
  tests/test_handicap.py, tests/test_api.py
frontend/             Vite + React single-page app — scaffolding, see step 3
  src/App.jsx         the form, its state, and the submit handler
  src/api.js          the only module that talks to the backend
  src/ResultCard.jsx  renders a result
```
The `backend/` directory exists from step 1 so the frontend has an obvious home
later and nothing needs moving.

## Conventions
- Keep the calculation logic backend-only and framework-free — it should be
  importable and testable without spinning up FastAPI. The dependency arrow
  points one way: `api` imports `golf`, never the reverse.
- **Validate at both altitudes.** Pydantic models reject bad input at the HTTP
  boundary (a clean 422); `golf/` keeps its own `ValueError` guards for
  non-HTTP callers. Import the bounds from `golf.handicap` rather than
  retyping them, so the two can't drift.
- **New analytics go in `backend/golf/` as pure functions over lists of round
  records**, with pytest tests written first against known-correct values. Same
  rule as `handicap.py`: no framework, no I/O, no database access. The stats
  layer is the part worth proving correct.
- **Store raw inputs; derive everything else on read.** Differentials, course
  handicaps and expected scores are computed, never persisted as the source of
  truth — otherwise a formula fix leaves the database disagreeing with the code.
- Prefer explicit, readable code over clever one-liners; this is a learning
  project.
- Update this file when a decision changes (e.g. swapping Railway for
  something else) so future sessions stay consistent. Product direction and
  feature scope changes go in `ROADMAP.md`.
