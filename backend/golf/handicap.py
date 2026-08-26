"""Single-round golf math, per the World Handicap System (WHS).

This module is deliberately framework-free: no FastAPI, no database, no I/O.
It is plain Python that can be imported and tested on its own, which is what
makes it the one layer of this app we can prove correct.

Everything here answers a question about ONE round on ONE tee. Questions that
need a scoring record -- what you typically shoot, what you shoot when you play
well -- live in `scoring.py`, which works on lists of the differentials this
module produces.

The formulas
------------
    Score Differential = (113 / Slope) x (Adjusted Gross Score - Course Rating - PCC)
    Course Handicap    = Handicap Index x (Slope / 113) + (Course Rating - Par)

The app computes no Handicap Index
----------------------------------
There is no `potential_score(handicap_index, ...)` here, and there was: it took
an index and returned the score that index posts when it plays well. The index
argument was the problem. An index is the mean of the best 8 of your last 20
differentials, and computing one from gross scores -- with no net double bogey
cap and none of the WHS safeguards -- produces a figure that looks exactly like
a handicap to anyone who asks how it works, while being about 1-1.5 strokes off
one. A recognisable formula with pieces missing reads as a half-finished
handicap rather than as a different measure chosen on purpose.

So the app stopped computing one. Potential is now the 20th percentile of your
differentials and typical is the median -- see the docstring in `scoring.py`.
Neither needs an index, because a Score Differential does not: it is a function
of the score, the rating, the slope and the PCC alone.

`course_handicap` and `playing_handicap` survive that decision because they are
not that. They convert an *official*, externally-issued index into strokes for
a match -- a number a player reads off their GHIN account and types in on the
day, never one this app derives. Allocating strokes between players is the one
job our own figures may not do, and these two are how the future net match
calculator does it without them.

A note on 0.96
--------------
The old USGA system multiplied by 0.96 (the "bonus for excellence") when
computing a Handicap Index from differentials. The WHS removed that in 2020.
It does not appear anywhere below, and should not be re-added. Handicap
allowances (95%, 85%, ...) are a different, still-current thing -- see
`playing_handicap`.
"""

from decimal import ROUND_HALF_UP, Decimal

# The slope rating of a course of "standard" difficulty. This is the 113 that
# shows up in every formula above: it is what the ratios are normalised against.
STANDARD_SLOPE = 113

# The range of slope ratings the WHS allows.
MIN_SLOPE = 55
MAX_SLOPE = 155


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _round_half_up(value: float, decimal_places: int = 0) -> float:
    """Round half away from zero, the way golf (and school arithmetic) does.

    Python's built-in round() uses *banker's rounding*, which rounds a halfway
    value to the nearest EVEN number: round(10.5) is 10, not 11. Golf rounds
    halves up, so a Course Handicap of exactly 10.5 must become 11. Using the
    built-in here would produce off-by-one handicaps.

    Decimal(str(value)) rather than Decimal(value) matters: building a Decimal
    straight from a float carries the float's binary representation error along
    with it (Decimal(10.5) is fine, but Decimal(2.675) is 2.67499999...).
    """
    quantum = Decimal(1).scaleb(-decimal_places)  # 1, 0.1, 0.01, ...
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _validate_slope(slope_rating: float) -> None:
    if not MIN_SLOPE <= slope_rating <= MAX_SLOPE:
        raise ValueError(
            f"slope_rating must be between {MIN_SLOPE} and {MAX_SLOPE}, got {slope_rating}"
        )


def _validate_course_rating(course_rating: float) -> None:
    if course_rating <= 0:
        raise ValueError(f"course_rating must be positive, got {course_rating}")


def _validate_par(par: int) -> None:
    if par <= 0:
        raise ValueError(f"par must be positive, got {par}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_differential(
    adjusted_gross_score: float,
    course_rating: float,
    slope_rating: float,
    pcc: float = 0.0,
) -> float:
    """How good a round actually was, on a neutral scale.

    This is the number that makes an 88 on a brutal course comparable to an 88
    on an easy one, and it is the input to everything in `scoring.py`. Rounded
    to one decimal place, per WHS.

    `pcc` is the Playing Conditions Calculation -- a course-wide adjustment for
    the day's weather and setup. It defaults to 0.0 and you will almost never
    set it by hand; it is a parameter so the signature matches the real formula.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)

    raw = (STANDARD_SLOPE / slope_rating) * (
        adjusted_gross_score - course_rating - pcc
    )
    return _round_half_up(raw, 1)


def course_handicap(
    handicap_index: float, slope_rating: float, course_rating: float, par: int
) -> int:
    """The number of strokes an official Handicap Index receives on this tee.

    WHS: HI x (Slope / 113) + (Course Rating - Par), rounded to a whole number.

    `handicap_index` must be an official, externally-issued index -- see the
    module docstring. Nothing this app calculates belongs in this argument.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)
    _validate_par(par)

    raw = handicap_index * (slope_rating / STANDARD_SLOPE) + (course_rating - par)
    return int(_round_half_up(raw))


def playing_handicap(course_hcp: int, allowance: float = 1.0) -> int:
    """Apply a competition format's handicap allowance to a Course Handicap.

    Allowances are set by format -- 95% for individual stroke play, 85% for
    four-ball, and so on. The default of 1.0 (100%) leaves the handicap alone.

    This is NOT the retired 0.96 "bonus for excellence"; see the module
    docstring.
    """
    if allowance < 0:
        raise ValueError(f"allowance must not be negative, got {allowance}")

    return int(_round_half_up(course_hcp * allowance))
