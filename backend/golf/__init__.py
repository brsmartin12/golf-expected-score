"""Golf scoring math.

Re-exports the public functions so callers can `from golf import score_differential`
instead of reaching into the module path.

Two modules, split by what they take: `handicap` answers questions about a
single round, `scoring` answers questions about a scoring record.
"""

from golf.handicap import (
    MAX_SLOPE,
    MIN_SLOPE,
    STANDARD_SLOPE,
    course_handicap,
    playing_handicap,
    score_differential,
)
from golf.scoring import (
    MINIMUM_ROUNDS,
    POTENTIAL_QUANTILE,
    TYPICAL_QUANTILE,
    WINDOW,
    potential_differential,
    quantile,
    score_from_differential,
    trailing,
    typical_differential,
)

__all__ = [
    "MAX_SLOPE",
    "MIN_SLOPE",
    "MINIMUM_ROUNDS",
    "POTENTIAL_QUANTILE",
    "STANDARD_SLOPE",
    "TYPICAL_QUANTILE",
    "WINDOW",
    "course_handicap",
    "playing_handicap",
    "potential_differential",
    "quantile",
    "score_differential",
    "score_from_differential",
    "trailing",
    "typical_differential",
]
