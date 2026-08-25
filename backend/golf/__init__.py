"""Golf handicap calculations.

Re-exports the public functions so callers can `from golf import potential_score`
instead of reaching into the module path.
"""

from golf.handicap import (
    MAX_SLOPE,
    MIN_SLOPE,
    STANDARD_SLOPE,
    course_handicap,
    potential_score,
    playing_handicap,
    score_differential,
    strokes_vs_potential,
)

__all__ = [
    "MAX_SLOPE",
    "MIN_SLOPE",
    "STANDARD_SLOPE",
    "course_handicap",
    "potential_score",
    "playing_handicap",
    "score_differential",
    "strokes_vs_potential",
]
