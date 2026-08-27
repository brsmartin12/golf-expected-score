# Golf Expected Score

Log a round — course, tee, date, score — and see what it was actually worth, so
a "bad" score on a hard course can be seen for what it is.

The point is what only your *history* can tell you. Two numbers, both quantiles
of your own Score Differentials:

- **typical** — the median. What you usually shoot here.
- **potential** — the 20th percentile. What you shoot when you play well.

A Handicap Index gives you only the second one, and only slowly. It is also not
what this app computes: our figures come from gross scores, where the World
Handicap System caps each hole at net double bogey, so calling ours an index
would be claiming a precision it does not have. A percentile has nothing missing
from it — "the median of your last 20 rounds" is the whole answer to how it
works. See **[ROADMAP.md](ROADMAP.md)**.

Partway through **step 5**: the calculation core, a FastAPI wrapper, a migrated
database, and a three-tab React app that logs rounds and grades them.

## Layout

```
ROADMAP.md              where this is going, and why
backend/
  golf/handicap.py      single-round math (framework-free, no I/O)
  golf/scoring.py       typical and potential, over a list of differentials
  api/main.py           the app object, health checks, error handling
  api/routers/          the routes that do the work — courses, rounds
  api/schemas.py        request/response models
  tests/
frontend/
  src/main.jsx          route table
  src/App.jsx           the shell: current route plus navigation
  src/routes/           one file per tab — LogRound, Rounds, Group
  src/styles/tokens.css every colour, size and space, in one place
  src/api.js            the only module that talks to the backend
```

`api` imports `golf`; `golf` imports nothing from `api`. The math stays testable
without a web server.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`pip install -e .` is an *editable* install: it points Python at this source
directory rather than copying files, so `import golf` works from anywhere in the
project and your edits take effect without reinstalling.

## Running the tests

```bash
cd backend
pytest -v          # -v names each case, so the suite reads as a spec
```

Tests use their own `<name>_test` database, created automatically, so a test run
never touches data you have entered while using the app. Database tests skip
with an explanatory message when Postgres is not running.

## The database

```bash
docker compose up -d      # start Postgres 16 on :5432
docker compose down       # stop it, keeping the data
```

The app finds it through `DATABASE_URL`, which defaults to the compose setup, so
nothing needs configuring to get started. To point somewhere else — a local
install, or a hosted Supabase/Neon database — copy `backend/.env.example` to
`backend/.env` and change it there.

Confirm it is reachable with `curl localhost:8000/health/db` once the API is
running, or just run the tests: the database tests skip with an explanatory
message when Postgres is not up, rather than failing.

Create or update the tables with:

```bash
cd backend && alembic upgrade head
```

Alembic replays an ordered list of schema changes and records which one the
database is at, so it can bring an existing database forward **without
destroying the rows in it** — which `create_all` cannot, because it only ever
creates and silently ignores a table that is already there.

If the database already has tables but Alembic has never run against it — a
database built before migrations existed — tell Alembic where it stands before
upgrading, or it will try to create tables that are already there:

```bash
alembic stamp head    # once, on a pre-existing database only
```

After changing anything in `db/models.py`:

```bash
alembic revision --autogenerate -m "what changed"   # writes a migration
alembic upgrade head                                # applies it
```

Read what autogenerate writes before committing it. It is reliable for columns,
types and indexes, and blind to intent — a renamed column is emitted as a drop
plus an add, which would throw the data away. `tests/test_migrations.py` fails
if the models and the migrations ever disagree.

## Running the API

```bash
cd backend
uvicorn api.main:app --reload
```

Then open <http://127.0.0.1:8000/docs> — FastAPI generates an interactive page
from the type hints where you can fire real requests at the endpoints.

| Method | Route             | Does                                                          |
| ------ | ----------------- | ------------------------------------------------------------- |
| GET    | `/health`         | Liveness check — deliberately does not touch the database      |
| GET    | `/health/db`      | Readiness check — can the app reach Postgres?                  |
| GET    | `/courses`        | Courses with their tees — what a course picker renders          |
| POST   | `/courses`        | Add a course and its tees together                              |
| GET    | `/rounds`         | Your rounds, most recently *played* first                       |
| POST   | `/rounds`         | Log a round and get the verdict in the same response            |

There is deliberately no calculator endpoint. Every number the app shows comes
from a golfer's own rounds, so it hangs off `/rounds`:

```bash
curl -X POST http://127.0.0.1:8000/rounds \
  -H 'Content-Type: application/json' \
  -d '{"tee_id": 1, "played_on": "2025-06-14", "gross_score": 80}'

# {"gross_score":80,"score_differential":8.0,"rounds_of_history":8,
#  "typical_score":76.5,"potential_score":74.4,
#  "to_typical":3.5,"to_potential":5.6, ...}
```

`to_typical` and `to_potential` read the way a scorecard does: negative is
better. Both are null until there are eight earlier rounds to draw on — nines
count the same as eighteens — and
`rounds_until_benchmarks` counts down to that.

Nine-hole rounds carry `"nine": "front"` or `"back"` and are graded on that
nine's scale, against a typical *nine*. They need the tee's published nine-hole
Course Rating and Slope, which the USGA lists per tee as "Front (9)" and
"Back (9)"; without them the round is logged and listed but not rated, because
approximating those figures costs more accuracy than including the round buys.
See ROADMAP.md.

## Running the frontend

The frontend needs the API running, so start that first (above), then in a
second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Add a course with its tees, then log a round — it
comes back graded in the same response.

The backend URL defaults to `http://127.0.0.1:8000`. To point somewhere else,
copy `.env.example` to `.env` and set `VITE_API_URL` — that's the hook step 9
uses to aim the deployed frontend at the deployed backend.

## Using the math directly

```python
from golf import (
    potential_differential,
    score_differential,
    score_from_differential,
    typical_differential,
)

# One round: how it rates, on a scale that is the same everywhere.
score_differential(88, 71.5, 130)          # 14.3

# A scoring record: the two quantiles, oldest round first.
history = [14.3, 11.0, 16.2, 12.8, 15.1, 13.4, 18.0, 12.1]
typical_differential(history)              # 13.9  -- the median
potential_differential(history)            # 12.4  -- the 20th percentile

# Back into strokes on the tee you are standing on.
score_from_differential(13.9, 71.5, 130)   # 87.5
```

Both quantiles return `None` below eight rounds rather than a number nobody
should trust.
