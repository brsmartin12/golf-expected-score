# Golf Score Differential App

## What this project is
A web app that replaces a personal spreadsheet. A golfer logs a round — course,
tee, date, score — and the app tells them what it was actually worth, so a "bad"
score on a hard course can be seen for what it is: possibly a strong round.

Core formula (USGA / World Handicap System):
- Score Differential = (Score − Course Rating − PCC) × 113 / Slope Rating

That is the only formula the app needs, and it is worth seeing why: a
differential is a function of the score, the rating, the slope and the PCC
**alone**. No handicap enters it. Everything the app shows is a quantile of a
golfer's own differentials, converted back into a score on the tee they played.

**Two numbers, one calculation.**
- **typical** = the median of your differentials — what you usually shoot. It
  headlines the round card.
- **potential** = the 20th percentile — the round you shoot when you play well.

"Potential", never "expected", for the good round; "typical" for the middle one.
Getting those two words backwards is the mistake the naming exists to prevent.
See Tier 2 in `ROADMAP.md`.

The *product name* is a separate matter and is still unchosen. "Golf Expected
Score" survives as a placeholder in the `<h1>`, the FastAPI title and the repo
name — deliberately, not as a missed rename. A title is not a claim about the
math. Leave it until a real name exists.

**But the calculator is not the product.** The USGA already ships that, and the
app no longer has one. The product is what you can only say once rounds
accumulate. A Handicap Index is the average of your *best 8 of the last 20*
differentials, so it measures **potential**, not expectation — the round you
shoot when you play well, with your *typical* round about 3 strokes worse. An
index shows you only that one number, and only slowly. The app's job is to show
both, to estimate how you are playing **right now**, and to surface consistency
and course fit, which an index throws away entirely.

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
- **Score-only entry.** A round is date + course + tee + total score, plus which
  nine if it was not all eighteen. No hole-by-hole, no fairways/GIR/putts.
  Data-entry friction is what kills golf apps; a round must stay a 15-second
  entry.
- **Nine-hole rounds are first-class.** People play nine when time is short, and
  a round the app refuses to grade is a round they stop logging. A nine is rated
  against that nine's own published Course Rating and Slope, then folded onto
  the 18-hole scale with a spread correction — see `golf/scoring.py`, and the
  section in `ROADMAP.md` for why doubling and the WHS's own method both distort
  potential. Nines count toward the round minimum exactly like eighteens: a
  golfer who only ever plays nine holes still gets both figures.
- **Multi-user from the schema up.** This is for the developer *and golf
  friends*, so `user_id` exists from the first table, even before auth ships.
  Groups themselves are *additive* — two new tables, no changes to existing
  ones — so they are built with auth at step 10, not before. See Tier 5 in
  `ROADMAP.md` for the schema and the three problems the leaderboard has to
  solve that the schema cannot.
- **Headline feature is the current-form index** (step 7 below). Earlier steps
  exist to make it possible.
- **Two moments, not one app.** Before the round (what should I shoot here,
  read-only) and after it (log in 15 seconds, get an instant verdict). Both
  happen at the course on a phone, often on bad signal. Every screen and
  endpoint should belong clearly to one of them — see `ROADMAP.md`, which is
  also precise about which connectivity failure a local draft does and does not
  solve. The group boards at step 10
  are the one exception: a third, unhurried context, read away from the course
  and likely screenshotted into a group chat.

## Build order (do not skip ahead)
1. Pure Python calculation functions (potential score, differential) + pytest
   unit tests against known-correct values. No web framework yet. **Done.**
2. Wrap the functions in a FastAPI app with a couple of REST endpoints.
   Verify via FastAPI's auto-generated /docs page. **Done.**
3. Minimal single-page React frontend: a form that calls the API and displays
   the result. **Done, and since replaced.** It was a handicap-index calculator
   — the thing `ROADMAP.md` opens by saying should not exist twice — and it went
   with the index. What survived is what Tier 0 said would: `api.js`, the env
   wiring, and the to-par display convention.
4. Add Postgres with SQLAlchemy as the ORM. Tables: `users`, `courses`, `tees`,
   `rounds` — see the schema in `ROADMAP.md`. **Done** — connection, sessions,
   models, API wiring (`/courses`, `/rounds`) and Alembic migrations. Two things
   are much cheaper now than later:
   - `tees` is its own table, not a column on `courses`. Slope and rating are
     per-tee — and each nine has its own pair on top of that, nullable, because
     the two nines are rated separately and their slopes routinely differ.
   - `rounds.played_on` is the date the round was **played**, not entered, and
     that is what makes point-in-time grading possible: every round is judged on
     the rounds played before it. Never grade history against *today's* numbers
     — that silently rewrites every past round and destroys every trend.
5. **Backfill the ~30 rounds of history**, deliberately this early: with no
   backfill the app has zero rounds and can say nothing interesting for a full
   season. This is what makes steps 6–8 useful on day one. The history is in
   18Birdies, which has no export, so this is hand entry — meaning the work is
   *quick-add entry UX*, not a CSV parser. Do import the existing spreadsheet,
   but as seed data for `courses` and `tees`; it is a calculator, not a record
   of scores.
6. Score-only analytics, as pure functions in `backend/golf/` (test-first, same
   as step 1). Typical and potential are **done** — `golf/scoring.py`. Still to
   come: round percentile ("you shoot this or better 26% of the time"),
   what-if projection ("shoot 84 and your typical goes 89.2 → 88.9"),
   cross-course score translation, pre-round target card.
7. **Current form** — the headline. Recency-weighted estimate of centre and
   spread over your differentials, shown against the flat 20-round figures
   ("usually 88, playing like an 85"), plus consistency as a first-class stat
   and trends reported with honest error bars.
8. Course fit, done honestly: per-course and per-tee strokes-vs-potential,
   shrunk toward zero with confidence intervals, so "this course suits your
   game" is only claimed when the data supports it — and says "need 4 more
   rounds here" when it doesn't.
9. Deploy: backend + DB to Railway/Render, frontend to Vercel. Wire the
   frontend to the deployed backend URL via an environment variable.
10. Auth (Supabase Auth or Clerk) + groups, so friends can use it with their
    own data. Then two group boards — a **form table** ranked on who is playing
    better than their *own* normal right now, and a **season table** ranked on
    the rate of rounds that beat your potential (the *rate*, not the average:
    the average gap to potential is ≈ 0.93σ, a fixed multiple of the player's
    own spread, so ranking on it is ranking on consistency) — and a
    net match calculator (the math for which is already in `handicap.py`). The form
    metric is a pure function over differentials and belongs in `backend/golf/`
    with step 7, since it shares the same recency-weighted machinery; only the
    grouping and the screen wait for step 10. See Tier 5 in `ROADMAP.md`.
11. (Future) Automatic integration to pull slope and rating values for courses
    from their various tee boxes; real PCC from historical weather.

## Project layout
```
ROADMAP.md            product vision and feature tiers — the "why"
backend/
  pyproject.toml      package metadata; `pip install -e ".[dev]"` to set up
  golf/handicap.py    single-round math: differential, course handicap
  golf/scoring.py     quantiles over a scoring record: typical, potential,
                      and the nine-hole scale correction
  api/main.py         FastAPI routes; api/schemas.py holds the Pydantic models
  db/session.py       SQLAlchemy engine + session factory; reads DATABASE_URL
  db/models.py        the tables: users, courses, tees, rounds
  db/config.py        where DATABASE_URL comes from; no side effects on import
  migrations/         Alembic; `alembic upgrade head` builds the schema
  api/routers/        courses.py and rounds.py, mounted in main.py
  api/deps.py         get_current_user — the seam auth replaces at step 10
  tests/              handicap, scoring, api, db, models, routes_data
frontend/             Vite + React, React Router, three tabs
  src/main.jsx        route table
  src/App.jsx         the shell: current route plus bottom navigation
  src/routes/         one file per tab — LogRound, Rounds, Group
  src/styles/tokens.css  design tokens; restyling happens here, not in components
  src/api.js          the only module that talks to the backend
```
The `backend/` directory exists from step 1 so the frontend has an obvious home
later and nothing needs moving.

## Conventions
- Keep the calculation logic backend-only and framework-free — it should be
  importable and testable without spinning up FastAPI. The dependency arrow
  points one way: `api` imports `golf` and `db`; neither imports `api`, and
  `golf` imports nothing outside itself and the standard library.
  Within `golf`, `scoring` imports `handicap` and not the reverse — one round
  is the smaller idea, a scoring record is built out of many of them.
- **Database tests skip rather than fail** when no database is reachable — see
  `requires_database` in `tests/conftest.py`. A fresh clone can always run
  `pytest` and watch the maths pass without starting Postgres first.
- **Tests run against a separate `<name>_test` database**, created on demand by
  `tests/conftest.py`. Development data is never touched by a test run, and
  tests never fail because of rows left over from using the app. This is why
  `db/config.py` is separate and why `db/__init__.py` exports the connection
  objects lazily: the redirect has to happen before any Engine exists.
- **Negative is good, in everything a golfer sees.** A minus sign already means
  "under par", so every stroke-denominated number on a screen uses that
  orientation — the round card, the form table, the season table, anything
  added later — as `to_typical` and `to_potential` do. An analysis primitive may
  run the other way where higher-is-better reads more naturally for averaging,
  but is then never displayed raw: the API exposes a separate display-oriented
  field beside it. See the display convention in `ROADMAP.md`.
- **Validate at both altitudes.** Pydantic models reject bad input at the HTTP
  boundary (a clean 422); `golf/` keeps its own `ValueError` guards for
  non-HTTP callers. Import the bounds from `golf.handicap` rather than
  retyping them, so the two can't drift.
- **New analytics go in `backend/golf/` as pure functions over lists of round
  records**, with pytest tests written first against known-correct values. Same
  rule as `handicap.py`: no framework, no I/O, no database access. The stats
  layer is the part worth proving correct.
- **Never approximate a rating.** If the published Course Rating and Slope for
  what was actually played are missing, the round is carried through ungraded
  and the screen says what to enter. Substituting a nearby number is worse than
  leaving the round out: at a tee whose nines are 116 and 105, using the 18-hole
  slope costs up to 0.87 strokes, several times what including the round gains.
- **Schema changes go through Alembic, never `create_all`.** `create_all` only
  ever creates, so it silently does nothing to a table that already exists.
  After changing a model, run `alembic revision --autogenerate -m "..."`, read
  what it wrote, and commit it with the model change. `tests/test_migrations.py`
  fails if the two ever disagree.
- **The app computes no handicap index, and nothing may be labelled one.**
  Potential is the 20th percentile of your own Score Differentials, typical the
  median — one calculation, two quantiles, and a Score Differential needs no
  index. That way "how is this worked out?" has a one-sentence answer instead of
  looking like the handicap formula with pieces missing.
- **The app's figures never allocate strokes between players.** We take gross
  scores; GHIN caps each hole at net double bogey, and that bias scales with how
  often a player blows up — two golfers GHIN rates 0.24 apart can come out 2.4
  apart here. It cancels in every self-referential comparison and does not cancel
  between people. Stroke-giving needs Adjusted Gross Scores or an agreed official
  index. See `ROADMAP.md`.
- **Store raw inputs; derive everything else on read.** Differentials, typical
  and potential are computed, never persisted as the source of truth —
  otherwise a formula fix leaves the database disagreeing with the code. This is
  also why a round is graded by `_read_models` over the whole series rather than
  row by row: its verdict depends on the rounds around it, not on itself.
- Prefer explicit, readable code over clever one-liners; this is a learning
  project.
- Update this file when a decision changes (e.g. swapping Railway for
  something else) so future sessions stay consistent. Product direction and
  feature scope changes go in `ROADMAP.md`.
