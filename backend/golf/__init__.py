"""Golf handicap calculations.

Re-exports the public functions so callers can `from golf import expected_score`
instead of reaching into the module path.
"""

from golf.handicap import (
    MAX_SLOPE,
    MIN_SLOPE,
    STANDARD_SLOPE,
    course_handicap,
    expected_score,
    playing_handicap,
    score_differential,
    strokes_vs_expected,
)

__all__ = [
    "MAX_SLOPE",
    "MIN_SLOPE",
    "STANDARD_SLOPE",
    "course_handicap",
    "expected_score",
    "playing_handicap",
    "score_differential",
    "strokes_vs_expected",
]
