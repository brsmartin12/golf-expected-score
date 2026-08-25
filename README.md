# Golf Expected Score

Enter a handicap index plus a course's slope and rating, and see the potential
score for that handicap on that tee — so a "bad" score on a hard course can be
seen for what it actually is.

The calculator is the starting point, not the goal — the USGA already has one of
those. The aim is what only your *history* can tell you: a Handicap Index is the
average of your best 8 of the last 20 rounds, so it measures your **potential**,
not your typical score. This app is being built to show both, to estimate how
you're playing *right now* rather than 20 rounds ago, and to find the courses
that suit your game. See **[ROADMAP.md](ROADMAP.md)**.

Currently partway through **step 4** of the build order in `CLAUDE.md`: the
calculation core, a FastAPI wrapper, a React form that calls it, and a database
connection. No tables yet.

## Layout

```
ROADMAP.md              where this is going, and why
backend/
  golf/handicap.py      all the math (framework-free, no I/O)
  api/main.py           HTTP routes over that math
  api/schemas.py        request/response models
  tests/
frontend/
  src/App.jsx           the form and its state
  src/api.js            the only module that talks to the backend
  src/ResultCard.jsx    renders a result
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
| POST   | `/potential-score` | Index + slope + rating → potential score, course handicap      |
| POST   | `/round`          | A played score → potential, strokes vs. potential, differential |

```bash
curl -X POST http://127.0.0.1:8000/round \
  -H 'Content-Type: application/json' \
  -d '{"score": 88, "handicap_index": 10.0, "slope_rating": 130, "course_rating": 71.5}'

# {"score":88.0,"potential_score":83.0,"strokes_vs_potential":-5.0,
#  "score_differential":14.3,"beat_expectation":false}
```

## Running the frontend

The frontend needs the API running, so start that first (above), then in a
second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Enter a handicap index, slope and course rating to
see what you shoot here when you play well; add a score to grade a round you played.

The backend URL defaults to `http://127.0.0.1:8000`. To point somewhere else,
copy `.env.example` to `.env` and set `VITE_API_URL` — that's the hook step 9
uses to aim the deployed frontend at the deployed backend.

## Using the math directly

```python
from golf import potential_score, score_differential, strokes_vs_potential

potential_score(10.0, 130, 71.5)        # 83.0  -- what a 10.0 index should shoot
score_differential(88, 71.5, 130)      # 14.3  -- how that round rates
strokes_vs_potential(88, 10.0, 130, 71.5)   # -5.0 -- five worse than potential
```

`strokes_vs_potential` is positive when you beat your expectation.
