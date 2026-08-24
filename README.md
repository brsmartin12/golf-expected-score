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

Currently at **step 1** of the build order in `CLAUDE.md`: the calculation core
and its tests. No web framework, no database, no frontend yet.

## Layout

```
ROADMAP.md              where this is going, and why
backend/
  golf/handicap.py      all the math (framework-free, no I/O)
  tests/test_handicap.py
frontend/               (step 3)
```

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

## Using it

```python
from golf import expected_score, score_differential, strokes_vs_expected

expected_score(10.0, 130, 71.5)        # 83.0  -- what a 10.0 index should shoot
score_differential(88, 71.5, 130)      # 14.3  -- how that round rates
strokes_vs_expected(88, 10.0, 130, 71.5)   # -5.0 -- five worse than expected
```

`strokes_vs_expected` is positive when you beat your expectation.
