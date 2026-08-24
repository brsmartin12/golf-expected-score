# Golf Expected Score

Enter a handicap index plus a course's slope and rating, and see the expected
score for that handicap on that tee — so a "bad" score on a hard course can be
seen for what it actually is.

The calculator is the starting point, not the goal — the USGA already has one of
those. The aim is what only your *history* can tell you: a Handicap Index is the
average of your best 8 of the last 20 rounds, so it measures your **potential**,
not your typical score. This app is being built to show both, to estimate how
you're playing *right now* rather than 20 rounds ago, and to find the courses
that suit your game. See **[ROADMAP.md](ROADMAP.md)**.

Currently at **step 2** of the build order in `CLAUDE.md`: the calculation core
and a FastAPI wrapper over it. No database and no frontend yet.

## Layout

```
ROADMAP.md              where this is going, and why
backend/
  golf/handicap.py      all the math (framework-free, no I/O)
  api/main.py           HTTP routes over that math
  api/schemas.py        request/response models
  tests/
frontend/               (step 3)
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

## Running the API

```bash
cd backend
uvicorn api.main:app --reload
```

Then open <http://127.0.0.1:8000/docs> — FastAPI generates an interactive page
from the type hints where you can fire real requests at the endpoints.

| Method | Route             | Does                                                          |
| ------ | ----------------- | ------------------------------------------------------------- |
| GET    | `/health`         | Liveness check                                                 |
| POST   | `/expected-score` | Index + slope + rating → expected score, course handicap       |
| POST   | `/round`          | A played score → expected, strokes vs. expected, differential  |

```bash
curl -X POST http://127.0.0.1:8000/round \
  -H 'Content-Type: application/json' \
  -d '{"score": 88, "handicap_index": 10.0, "slope_rating": 130, "course_rating": 71.5}'

# {"score":88.0,"expected_score":83.0,"strokes_vs_expected":-5.0,
#  "score_differential":14.3,"beat_expectation":false}
```

## Using the math directly

```python
from golf import expected_score, score_differential, strokes_vs_expected

expected_score(10.0, 130, 71.5)        # 83.0  -- what a 10.0 index should shoot
score_differential(88, 71.5, 130)      # 14.3  -- how that round rates
strokes_vs_expected(88, 10.0, 130, 71.5)   # -5.0 -- five worse than expected
```

`strokes_vs_expected` is positive when you beat your expectation.
