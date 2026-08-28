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
works — the long version is in **[METHOD.md](METHOD.md)**, along with every
known bias and its measured size. See **[ROADMAP.md](ROADMAP.md)** for where
this is going and why.

Partway through **step 5**: the calculation core, a FastAPI wrapper, a migrated
database, and a three-tab React app that logs rounds and grades them.

## Quick start

Needs Docker, Python 3.11+ and Node. Once, after cloning:

```bash
make setup      # virtualenv, backend deps, frontend deps
make start      # Postgres up, migrations applied
```

Then two terminals, both left running:

```bash
make api        # backend  -> http://127.0.0.1:8000   (/docs for the API)
make web        # frontend -> http://localhost:5173
```

Open <http://localhost:5173>, add a course with its tees, and log a round.

`make` on its own lists every target. Nothing is hidden — each one runs the
same commands the sections below explain, and `make -n <target>` prints what it
would do without doing it. What the Makefile really provides is the *order*,
which is the part that was easy to get wrong.

Day to day:

```bash
make test       # the test suite
make migrate    # after pulling a change to the models
make backup     # snapshot the database before anything risky
make stop       # stop Postgres, keeping the data
```

## Layout

```
Makefile                every command you need; `make` lists them
METHOD.md               how every number is worked out, and what it costs
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

## Setup, the long way

`make setup` runs exactly this, and is what you should use. It is spelled out
here because the pieces are worth recognising:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cd ../frontend
npm install
```

`pip install -e .` is an *editable* install: it points Python at this source
directory rather than copying files, so `import golf` works from anywhere in the
project and your edits take effect without reinstalling.

The `make` targets call `backend/.venv/bin/...` directly, so you never have to
activate anything. Forgetting to activate a virtualenv is the most common way
this goes wrong, and it fails confusingly — the commands exist, they just belong
to a different Python.

## Running the tests

```bash
make test          # or, from backend/: pytest -v
```

`-v` names each case, so the suite reads as a spec.

Tests use their own `<name>_test` database, created automatically, so a test run
never touches data you have entered while using the app. Database tests skip
with an explanatory message when Postgres is not running.

## The database

```bash
docker compose up -d      # start Postgres 16 on :5432
docker compose down       # stop it, keeping the data
docker compose down -v    # stop it and DELETE the data — see Backups below
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

### Merging a duplicated course

Courses are unique on name, city and state. Until recently that constraint let
duplicates through anyway: Postgres treats two NULLs as *different* values in a
unique constraint, and city and state are both optional, so entering the same
course twice with no location produced two rows and two entries in the picker.
The migration that fixes it refuses to run while duplicates exist, because
which row to keep is a judgement it should not make for you.

There is no screen for this — it is a one-off repair, and the app is otherwise
the only way data goes in. Take a snapshot first:

```bash
make backup
make psql
```

Find the duplicates and everything hanging off them. Rounds point at tees, tees
point at courses, so all three tables are involved:

```sql
SELECT c.id AS course_id, c.name, c.city, c.state,
       t.id AS tee_id, t.name AS tee, t.course_rating, t.slope_rating,
       t.front_course_rating, t.back_course_rating,
       count(r.id) AS rounds
FROM courses c
LEFT JOIN tees t ON t.course_id = c.id
LEFT JOIN rounds r ON r.tee_id = t.id
WHERE c.name IN (SELECT name FROM courses GROUP BY name, city, state
                 HAVING count(*) > 1)
GROUP BY c.id, c.name, c.city, c.state, t.id, t.name
ORDER BY c.name, c.id, t.name;
```

Then decide, from that output, which course id is the **keeper** — normally the
one whose tees are most complete, since ratings are the part that is tedious to
re-enter. Two cases follow, and a real duplicate usually needs both.

**A tee that exists only on the leftover course** moves across as it is:

```sql
UPDATE tees SET course_id = <keeper_course_id> WHERE id = <tee_id>;
```

**The same tee entered on both** — the usual case, where one copy has the
nine-hole ratings and the other does not — needs its rounds repointing before
the duplicate goes, or they would be deleted with it:

```sql
UPDATE rounds SET tee_id = <keeper_tee_id> WHERE tee_id = <duplicate_tee_id>;
DELETE FROM tees WHERE id = <duplicate_tee_id>;
```

Check that nothing is left pointing at the leftover course, then remove it:

```sql
SELECT count(*) FROM tees WHERE course_id = <leftover_course_id>;   -- expect 0
DELETE FROM courses WHERE id = <leftover_course_id>;
```

Leave the psql prompt with `\q`, then `make migrate`. The migration's guard is
the check that the merge was complete: if it still refuses, a duplicate remains.

Nothing above is destructive to scores as long as the rounds are repointed
first — and that is exactly the step to get wrong, which is what the backup at
the top is for. Once merged, a tee missing its nine-hole ratings no longer
needs a second course: **Add a course or tee → Nine ratings** fills them in on
the tee that is already there.

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
| POST   | `/courses/{id}/tees` | Add tees to a course that already exists                     |
| GET    | `/rounds`         | Your rounds, most recently *played* first                       |
| POST   | `/rounds`         | Log a round and get the verdict in the same response            |
| DELETE | `/rounds/{id}`    | Remove a round — the fix for a mistyped score                    |

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
better. Both are null until there are three earlier rounds to draw on — nines
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

## Backups

Your rounds live in one Docker volume on one machine. There is no other copy,
and the history came from 18Birdies, which has no export — so losing it means
re-entering every round by hand. `docker compose down -v` is one character away
from `docker compose down`.

Take a snapshot before anything that touches the database, and before a long
data-entry session:

```bash
docker compose exec -T db pg_dump -U golf golf > backup-$(date +%F).sql
```

**Then look at the file.** A dump of a database that was not running still
exits successfully and still creates a file — a few kilobytes of nothing. That
is the standard way a backup turns out to be worthless:

```bash
wc -l backup-*.sql        # a real one is hundreds of lines
```

To restore, into an **empty** database. A plain dump contains `CREATE TABLE`
statements, so restoring over existing tables fails part-way and leaves a mess:

```bash
docker compose down -v && docker compose up -d --wait
docker compose exec -T db psql -U golf -d golf < backup-2026-08-27.sql
```

`--wait` matters: `up -d` returns as soon as the container starts, which is
several seconds before Postgres accepts connections, and a restore fired into
that gap fails with "connection refused". The healthcheck in
`docker-compose.yml` is what `--wait` waits for.

The dump carries the `alembic_version` row with it, so a restored database
knows which migration it is on and `alembic upgrade head` works immediately.
Nothing needs stamping.

Why `pg_dump` and not something in this repo: it is complete, it is exact, and
it needs no maintenance. A hand-written exporter would be a partial
reimplementation of it that has to be updated with every migration or quietly
start dropping columns. There *is* a case for a JSON export — readable, easy to
diff, good for fixtures, and eventually a real "export my rounds" feature once
other people's data is in here — but that is a different job from not losing
anything, and it should not be confused for one.

Once deployed (step 9), the hosting provider takes automated backups and this
stops being a single-machine problem.

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

Both quantiles return `None` below three rounds. Not below one, which would be
tempting: with a single round the median and the 20th percentile are the same
number, so the card would show two identical figures and say nothing. See
METHOD.md.
