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

**See `METHOD.md`** for the maths: every formula, the reason it is that one
rather than an alternative, and the measured size of every bias we knowingly
carry. It is the answer to "how is this number worked out?" — keep it current
when a formula changes, since a stale one is worse than none.

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
  nine if it was not all eighteen. Never fairways/GIR/putts/shot tracking — the
  line is that nothing may require a golfer to record something they were not
  already writing down. Data-entry friction is what kills golf apps; a round must
  stay a 15-second entry. **Hole scores are the one reopened question** — they
  are eighteen numbers off a card that already exists, not a new thing to track,
  and they would unlock a capped score (which unblocks the match calculator) and
  per-hole typical/potential. Note the cap is *net* double bogey, so it still
  needs a handicap from somewhere — hole scores remove the arithmetic obstacle,
  not the circularity. Optional and additive, never
  required, and it is step 11. See Tier 6 in `ROADMAP.md` for the conditions
  and the additive schema.
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
- **The headline is the stat book** (step 7 below): the golfer's own scoring
  distribution, with current form read against it. Current form was the headline
  on its own until it became clear the distribution is what makes it legible —
  "playing like an 85" means nothing to someone who has not seen what "usually"
  looks like. Earlier steps exist to make it possible. See "The axis nobody is
  on" in `ROADMAP.md`: their unit of analysis is the round, ours is the golfer.
- **Two moments, not one app.** Before the round (what should I shoot here,
  read-only) and after it (log in 15 seconds, get an instant verdict). Both
  happen at the course on a phone, often on bad signal. Every screen and
  endpoint should belong clearly to one of them — see `ROADMAP.md`, which is
  also precise about which connectivity failure a local draft does and does not
  solve. The group boards at step 10
  are the one exception: a third, unhurried context, read away from the course
  and likely screenshotted into a group chat.
- **The two moments share one card.** Both show typical and potential on the tee
  in front of you; they differ only by the score input and the closing line. Build
  one component in two modes, not two screens — `VerdictCard` is already most of
  the pre-round card. The third tab is the target card; Group takes that slot at
  step 10. See "The two cards are one card" in `ROADMAP.md`.
- **A number is not a claim.** A per-course figure, shrunk toward your overall
  one, is defined from the first round and is always shown. An assertion about a
  difference — "this course is hard for you" — waits for evidence. Never gate a
  number behind the threshold that belongs to a claim. This generalises: every
  claim carries its own confidence, and saying "that is noise, keep logging" is
  the app's real differentiator, not a caveat on it. Golf apps imply confidence
  they have not earned; refusing to is what makes the unhedged numbers worth
  believing.

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
7. **The stat book** — the headline, and the app's home screen, which today is
   a form and should not be. Four things in order: typical and potential big at
   the top; **the distribution** underneath — the last 20 differentials as marks
   with both quantiles picked out, which is the picture that explains why a
   handicap sits below what you usually shoot; current form against the flat
   figure ("usually 88, playing like an 85"); and what the app does not know yet.
   Around them: range (typical − potential) as the consistency reading, blow-up
   rate, rust, nine-versus-eighteen, and records. Trends always with honest error
   bars. The distribution comes *before* current form deliberately — "playing
   like an 85" is meaningless until you have seen what "usually" looks like.
   See Tier 3 in `ROADMAP.md`.
8. Course fit, done honestly: per-course and per-tee strokes-vs-potential,
   shrunk toward zero with confidence intervals, so "this course suits your
   game" is only claimed when the data supports it — and says "need 4 more
   rounds here" when it doesn't.
9. Deploy: backend + DB to a managed platform, frontend to static hosting.
   **Deploy privately for one golfer first** — the app cannot do the thing it is
   for while it only runs on a laptop, and three small things block a first
   deploy today (hardcoded CORS origins, the shared `get_current_user` row, and
   nothing running migrations on deploy). See "What production means for this
   app" in `ROADMAP.md`.
   Wire the frontend to the deployed backend URL via an environment variable.
   Packaging and hosting are separate choices and most platforms take a
   Dockerfile — see "Deployment, and keeping dev and prod the same thing" in
   `ROADMAP.md`, which also lists what the repo has to pin and lock first.
10. Auth (Supabase Auth or Clerk) + groups, so friends can use it with their
    own data. Auth and groups are separate jobs — accounts are what sharing the
    app needs, boards are extra. See "The auth plan" in `ROADMAP.md`, which
    covers claiming the backfilled rounds without a data migration and the
    `email_verified` requirement that makes it safe. Then two group boards — a **form table** ranked on who is playing
    better than their *own* normal right now, and a **season table** ranked on
    the rate of rounds that beat your potential (the *rate*, not the average:
    the average gap to potential is ≈ 0.93σ, a fixed multiple of the player's
    own spread, so ranking on it is ranking on consistency) — and a
    net match calculator (the math for which is already in `handicap.py`). The form
    metric is a pure function over differentials and belongs in `backend/golf/`
    with step 7, since it shares the same recency-weighted machinery; only the
    grouping and the screen wait for step 10. See Tier 5 in `ROADMAP.md`.
11. **Hole-by-hole scores, if they earn it.** Optional per round, never
    required, and nothing in steps 6–8 may come to depend on them: a round with
    a total and no holes stays first-class. What they unlock is specific — real
    a capped score (which removes the measured gross-score bias in `METHOD.md`
    and is what currently blocks the step 10 match calculator, though net double
    bogey still needs a handicap from somewhere),
    typical and potential *per hole*, and the gap between your round potential
    and the sum of your per-hole potentials, which measures how much of your good
    golf is available on the same day. Two additive tables, `holes` and
    `hole_scores`; nothing existing changes. The gate is the entry screen: if
    eighteen holes cannot be entered about as fast as a total, it does not ship.
    See Tier 6 in `ROADMAP.md`.
12. (Future) Automatic integration to pull slope and rating values for courses
    from their various tee boxes; real PCC from historical weather.

## Project layout
```
METHOD.md             every formula, why it is that one, and its measured bias
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
- **A nine counts once for a quantile and half for a mean.** The √2 scaling in
  `golf/scoring.py` gives a scaled nine an eighteen's *distribution*, which is
  what typical and potential need. Anything that averages or puts an error bar
  on a window — the form delta, trend significance, course-fit shrinkage — must
  instead double the nine and weight it 0.5, and divide by `Σ weights` rather
  than the row count. Skip that and confidence intervals come out up to 20% too
  narrow. See the nine-hole section in `ROADMAP.md`.
- **Never approximate a rating.** If the published Course Rating and Slope for
  what was actually played are missing, the round is carried through ungraded
  and the screen says what to enter. Substituting a nearby number is worse than
  leaving the round out: at a tee whose nines are 116 and 105, using the 18-hole
  slope costs up to 0.87 strokes, several times what including the round gains.
- **Once deployed, migrations must survive a rolling deploy.** A deploy starts
  the new container before stopping the old one, so for a few seconds both
  versions run against the same schema. Dropping a column the old code still
  reads breaks live requests. Destructive changes then take two deploys:
  *expand* (add), ship the code that uses it, *contract* (remove) later. Every
  migration so far is a single destructive step, which was correct with nothing
  deployed and stops being correct the day something is. See `ROADMAP.md`.
- **Schema changes go through Alembic, never `create_all`.** `create_all` only
  ever creates, so it silently does nothing to a table that already exists.
  After changing a model, run `alembic revision --autogenerate -m "..."`, read
  what it wrote, and commit it with the model change. `tests/test_migrations.py`
  fails if the two ever disagree.
- **Gross scores in, never Adjusted Gross — while a round is a total.** The WHS
  caps each hole at net double bogey; we take the card, because a total cannot
  supply the cap. Not because it is circular: net double bogey needs a Course
  Handicap, but the WHS resolves that *recursively* — each round is capped
  against the index held before it — which is the traversal `played_on` ordering
  already performs. It also answers a question nobody asks about their own game.
  The cost is that typical reads 1.8–2.6 strokes high for anyone who blows up
  while potential barely moves, so our typical-to-potential gap runs ~1.7 wider
  than a WHS one. Never name a parameter or column `adjusted_*` — that was a
  real bug, and it read as a handicap breadcrumb. See `METHOD.md`.
- **No handicap index while a round is only a total; nothing is ever labelled an
  issued one.** Potential is the 20th percentile of your own Score
  Differentials, typical the median — one calculation, two quantiles, and a
  Score Differential needs no index. The original ban existed because
  best-8-of-20 over uncapped totals is the handicap formula with pieces missing;
  that is an argument about missing *data*, and hole scores (step 11) supply it.
  Once they do, compute it — never present it as issued, always beside a GHIN
  figure rather than instead of one, and never as the basis for typical and
  potential, which stay percentiles because percentiles are the better numbers.
  Derived on read like everything else; still no `handicap_snapshots`, still no
  `rounds.index_at_time`. See "The replacement rule" in `ROADMAP.md`.
- **Figures from uncapped scores never allocate strokes between players.** We
  take gross scores; GHIN caps each hole at net double bogey, and that bias
  scales with how often a player blows up — two golfers GHIN rates 0.24 apart can
  come out 2.4 apart here. It cancels in every self-referential comparison and
  does not cancel between people. **The cap is the fix, not the index**: an index
  over uncapped scores allocates just as unfairly. So stroke-giving needs capped
  scores from every player in the match — meaning every one of them has entered
  holes — or an agreed official index. Say which at the point of use; never
  substitute an uncapped figure quietly. See `ROADMAP.md`.
- **Store raw inputs; derive everything else on read.** Differentials, typical
  and potential are computed, never persisted as the source of truth —
  otherwise a formula fix leaves the database disagreeing with the code. This is
  also why a round is graded by `_read_models` over the whole series rather than
  row by row: its verdict depends on the rounds around it, not on itself.
- **The phone layout is the default; desktop is one media query.** Both of the
  app's moments happen at the course, so every screen is written mobile-first
  and `@media (min-width: 48rem)` in `index.css` adapts it — the column widens
  and the navigation moves from the bottom of the screen to the top. Not two
  components and not two stylesheets: a new screen gets the desktop treatment
  for free, and there is one place to look when it doesn't.
- **Never fake a font weight.** `font-synthesis: style` on `body` is load-
  bearing. Archivo Black is a single face declared at weight 400, so a request
  for 900 made the browser smear it wider and the verdict number's digits ran
  together. Display rules still ask for 900 — that is for the fallback stack —
  and the synthesis rule is what stops it being applied to the real face.
- Prefer explicit, readable code over clever one-liners; this is a learning
  project.
- Update this file when a decision changes (e.g. swapping Railway for
  something else) so future sessions stay consistent. Product direction and
  feature scope changes go in `ROADMAP.md`.
