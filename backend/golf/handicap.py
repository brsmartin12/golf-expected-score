"""Golf handicap and scoring math, per the World Handicap System (WHS).

This module is deliberately framework-free: no FastAPI, no database, no I/O.
It is plain Python that can be imported and tested on its own, which is what
makes it the one layer of this app we can prove correct.

The formulas
------------
    Score Differential = (113 / Slope) x (Adjusted Gross Score - Course Rating - PCC)
    Course Handicap    = Handicap Index x (Slope / 113) + (Course Rating - Par)
    Potential Score    = Handicap Index x (Slope / 113) + Course Rating

"Par + Course Handicap" and "Potential Score" are the same formula, not two
competing definitions -- the Par term cancels:

    Par + [ HI x (Slope/113) + (CR - Par) ]  ==  HI x (Slope/113) + CR

They differ only in rounding. Course Handicap is rounded to a whole number, so
`par + course_handicap(...)` is an integer while `potential_score(...)` keeps a
decimal; the two can sit up to half a stroke apart. Both are exposed so the UI
can show whichever reads better.

Why "potential" and not "expected"
----------------------------------
This number is widely called an "expected score", and that name is wrong in a
way that matters here. A Handicap Index is the mean of the best 8 of your last
20 Score Differentials -- 12 of the 20 are discarded before it is calculated. So
a round that produces a differential equal to your index is not a typical round
for you, it is a good one: roughly your top quartile.

Your *typical* score is higher. How much higher depends on your consistency --
for a roughly normal spread the mean of the best 8 of 20 sits around 0.8
standard deviations below the overall mean, so a streaky player's gap is wider
than a steady player's. That gap is not derivable from an index alone; it needs
a scoring record, which is what the analytics layer is being built for.

Calling it "potential" keeps the distinction visible, and pairs with the
"typical" figure that arrives once there are stored rounds.

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


def _handicap_strokes(handicap_index: float, slope_rating: float) -> float:
    """Handicap Index x (Slope / 113), unrounded.

    The shared core of both `potential_score` and `course_handicap`. Keeping it
    in one place is what makes the "Par + Course Handicap == Potential Score"
    identity hold by construction instead of by coincidence.

    Deliberately unrounded: rounding happens once, at the public boundary.
    Rounding an already-rounded number compounds the error (83.449 -> 83.4 ->
    83, but 83.449 -> 83 in one step... and 83.45 -> 83.5 -> 84 where a single
    rounding gives 83).
    """
    return handicap_index * (slope_rating / STANDARD_SLOPE)


def _potential_score_exact(
    handicap_index: float, slope_rating: float, course_rating: float
) -> float:
    """Potential score with no rounding applied. Used internally for comparisons."""
    return _handicap_strokes(handicap_index, slope_rating) + course_rating


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
    on an easy one. Rounded to one decimal place, per WHS.

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


def potential_score(
    handicap_index: float, slope_rating: float, course_rating: float
) -> float:
    """The score this Handicap Index posts on this course/tee when it plays well.

    NOT the typical score for this index -- see "Why potential and not expected"
    in the module docstring. A round matching this number is roughly a
    top-quartile round.

    Rounded to one decimal place. For the whole-stroke version, use
    `par + course_handicap(...)` -- same formula, integer rounding.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)

    return _round_half_up(
        _potential_score_exact(handicap_index, slope_rating, course_rating), 1
    )


def course_handicap(
    handicap_index: float, slope_rating: float, course_rating: float, par: int
) -> int:
    """The number of strokes this player receives on this course/tee.

    WHS: HI x (Slope / 113) + (Course Rating - Par), rounded to a whole number.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)
    _validate_par(par)

    raw = _handicap_strokes(handicap_index, slope_rating) + (course_rating - par)
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


def strokes_vs_potential(
    score: float, handicap_index: float, slope_rating: float, course_rating: float
) -> float:
    """How many strokes better than your potential this round was.

    POSITIVE means you BEAT your potential: shooting 79 where your potential is
    83.0 returns +4.0. This is the ANALYSIS orientation, where higher is better,
    so averaging it over a course or a season reads the natural way.

    Do not put this in front of a golfer -- a minus sign already means "under
    par" to them, so a negative here would label a bad round the way a good one
    is labelled. The API negates it into `to_potential` for display.

    Compares against the unrounded potential score, so the headline number never
    inherits a rounding artefact.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)

    potential = _potential_score_exact(handicap_index, slope_rating, course_rating)
    return _round_half_up(potential - score, 1)
