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
    Score Differential = (113 / Slope) x (Gross Score - Course Rating - PCC)
    Course Handicap    = Handicap Index x (Slope / 113) + (Course Rating - Par)

The WHS writes the first one with *Adjusted* Gross Score, and this app does not
use one. See "Gross, not Adjusted Gross" below -- a deliberate choice, not a
missing step.

No Handicap Index -- while a round is only a total
-------------------------------------------------
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

Note what that argument rests on: the pieces are missing because a TOTAL cannot
supply them. It is a statement about the data, not a principle, and it expires
if hole scores are ever recorded -- the cap becomes computable, the safeguards
always were, and an index gets computed then. It would still never be presented
as an issued one, and it would still not be the basis for typical and potential,
which stay percentiles because percentiles answer the question better. See "The
replacement rule" in ROADMAP.md.

`course_handicap` and `playing_handicap` survive that decision because they are
not that. They convert an index into strokes for a match -- today only an
*official*, externally-issued one, read off a GHIN account and typed in on the
day. The rule they enforce is about the CAP, not the naming: a figure derived
from uncapped scores may not allocate strokes between players, because the
blow-up bias cancels against yourself and does not cancel against someone else.
An index over uncapped scores would be just as ineligible. These two are how the
future net match calculator works once capped scores exist.

Gross, not Adjusted Gross
-------------------------
The WHS feeds this formula an Adjusted Gross Score: every hole capped at net
double bogey, which is par + 2 plus whatever handicap strokes you receive there.
We feed it the score on the card, and the golfer is NOT asked to adjust anything.

Two reasons, and the second is the real one.

The practical reason: a total does not contain the hole scores the cap needs,
and asking a golfer to work it out by hand would end the fifteen-second round
entry that the whole score-only scope decision exists to protect. Not that the
cap is circular -- net double bogey needs a Course Handicap, which needs an
index, but the WHS resolves that RECURSIVELY: each round is capped against the
index held before it, early rounds uncapped as the base case. That traversal is
what ordering rounds by `played_on` already performs.

The better reason: we are answering a different question. AGS exists to make
competition fair -- it stops one disaster hole wrecking a handicap that other
people will give strokes against. Nobody asks "what would I have shot if my
triple had been capped?" about their own game. Asked what you usually shoot, the
honest answer is the number on the card.

What it costs, measured over 4,000 simulated rounds per player:

    player                     typical   potential   the gap
    steady  (rare blow-ups)      +0.00       +0.00     +0.00
    typical (some blow-ups)      +1.80       +0.00     +1.80
    streaky (often blows up)     +2.60       +0.90     +1.70

Potential is barely touched, because a good round has few disasters to cap.
Typical carries the whole effect, so the gap between the two runs about 1.7
strokes wider here than a WHS-based figure would. Self-referential comparisons
are unaffected -- a round and the typical it is measured against are both
uncapped, so `to_typical` still reads true. It does not cancel between people,
which is one more reason these figures may not allocate strokes. See METHOD.md.

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
    gross_score: float,
    course_rating: float,
    slope_rating: float,
    pcc: float = 0.0,
) -> float:
    """How good a round actually was, on a neutral scale.

    This is the number that makes an 88 on a brutal course comparable to an 88
    on an easy one, and it is the input to everything in `scoring.py`. Rounded
    to one decimal place, per WHS.

    The first argument is the score as written on the card. It was named
    `adjusted_gross_score` once, after the WHS's own name for this input, and
    that was wrong in a way worth stating plainly: an Adjusted Gross Score caps
    every hole at net double bogey, we compute no such thing, and naming a
    parameter after a quantity we never produce invites the reader to assume we
    do. See "Gross, not Adjusted Gross" in the module docstring.

    `pcc` is the Playing Conditions Calculation -- a course-wide adjustment for
    the day's weather and setup. It defaults to 0.0 and you will almost never
    set it by hand; it is a parameter so the signature matches the real formula.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)

    raw = (STANDARD_SLOPE / slope_rating) * (gross_score - course_rating - pcc)
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
