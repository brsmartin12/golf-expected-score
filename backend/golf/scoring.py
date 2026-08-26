"""How a scoring record becomes the two numbers the app puts on screen.

Where handicap.py works on ONE round, this works on a list of them. It is the
first module in `golf/` shaped that way, and per the convention in CLAUDE.md it
stays pure: no framework, no I/O, no database — a list of numbers in, numbers
out.

Typical and potential, and why neither is a handicap
---------------------------------------------------
Both are quantiles of the golfer's own Score Differentials:

    typical   = the median          (half your rounds are better)
    potential = the 20th percentile (the round you shoot when you play well)

One calculation, two settings. That matters for more than tidiness. The app
deliberately does NOT compute a Handicap Index, because a figure worked out as
"best 8 of the last 20" is recognisably the WHS formula, and the first person to
ask how it works would find that formula with pieces missing — no net double
bogey cap, no safeguards — which reads as a half-finished handicap rather than a
different measure on purpose.

A percentile has no such problem. There is nothing absent from it. "Typical is
the median of your last 20 rounds, potential is your 20th percentile" is the
whole answer.

None of this needs an index, because a Score Differential does not: it is a
function of the score, the rating, the slope and the PCC alone. Two golfers of
very different ability who shoot the same score from the same tee produce the
same differential. So the chain runs

    rounds -> differentials -> quantiles -> a score on this tee

and never passes through a handicap at any point.

What the numbers may NOT be used for
------------------------------------
Allocating strokes between players. Because this app takes gross scores while
the WHS caps every hole at net double bogey, a golfer's figure here is inflated
in proportion to how often they blow up — two players a handicap system would
rate a quarter of a stroke apart can come out over two strokes apart here. That
cancels in every self-referential comparison (typical against potential, this
course against your overall) and does not cancel between people. See ROADMAP.md.
"""

from golf.handicap import STANDARD_SLOPE, _round_half_up, _validate_course_rating, _validate_slope

# The WHS looks at the last 20 rounds and so does this, which keeps typical and
# potential drawn from the same population as any official figure a golfer
# compares them against.
WINDOW = 20

# Below this, a quantile is more noise than signal — a median over five rounds
# moves about ±1.9 strokes, over eight about ±1.4. The screen shows a countdown
# instead of a number.
MINIMUM_ROUNDS = 8

TYPICAL_QUANTILE = 0.50
POTENTIAL_QUANTILE = 0.20


def quantile(values: list[float], q: float) -> float:
    """The q-th quantile, interpolating between the two nearest values.

    Written out rather than imported from statistics.quantiles, which splits a
    list into n buckets rather than answering for an arbitrary q, and whose
    edge behaviour on short lists is easy to get subtly wrong.
    """
    if not values:
        raise ValueError("quantile of an empty list is undefined")
    if not 0.0 <= q <= 1.0:
        raise ValueError(f"quantile must be between 0 and 1, got {q}")

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = q * (len(ordered) - 1)
    below = int(position)
    above = min(below + 1, len(ordered) - 1)
    return ordered[below] + (ordered[above] - ordered[below]) * (position - below)


def typical_differential(
    differentials: list[float], minimum_rounds: int = MINIMUM_ROUNDS
) -> float | None:
    """The middle of this golfer's scoring. None until there are enough rounds.

    The median rather than the mean: golf scores are right-skewed — a lost ball
    has no mirror image on the good side — so the mean is dragged upward by
    blow-ups and a player beats it 53-57% of the time rather than half. The
    median is beaten exactly half the time by construction, which is the whole
    reason it is fit to headline a round card.
    """
    return _quantile_or_none(differentials, TYPICAL_QUANTILE, minimum_rounds)


def potential_differential(
    differentials: list[float], minimum_rounds: int = MINIMUM_ROUNDS
) -> float | None:
    """The round this golfer plays when they play well. None until enough rounds."""
    return _quantile_or_none(differentials, POTENTIAL_QUANTILE, minimum_rounds)


def _quantile_or_none(
    differentials: list[float], q: float, minimum_rounds: int
) -> float | None:
    recent = differentials[-WINDOW:]
    if len(recent) < minimum_rounds:
        return None
    return _round_half_up(quantile(recent, q), 1)


def score_from_differential(
    differential: float, course_rating: float, slope_rating: float, pcc: float = 0.0
) -> float:
    """Turn a differential back into a score on a particular tee.

    The inverse of `score_differential`, and the same arithmetic the old
    index-based `potential_score` performed — an index was only ever an average
    of differentials under another name. Naming it for what it does removes the
    suggestion that a handicap is involved.
    """
    _validate_slope(slope_rating)
    _validate_course_rating(course_rating)

    return _round_half_up(
        differential * (slope_rating / STANDARD_SLOPE) + course_rating + pcc, 1
    )


def trailing(
    differentials: list[float],
    q: float,
    window: int = WINDOW,
    minimum_rounds: int = MINIMUM_ROUNDS,
) -> list[float | None]:
    """For each round, the quantile of the rounds BEFORE it.

    Oldest first. Position i is computed from at most `window` differentials
    ending at i-1, so a round is never judged against itself or against rounds
    that had not been played yet.

    That point-in-time discipline is the reason this exists rather than a single
    figure applied to every row: computing a golfer's whole history against
    today's numbers silently rewrites every past round and destroys every trend.
    """
    result: list[float | None] = []
    for i in range(len(differentials)):
        history = differentials[max(0, i - window) : i]
        result.append(
            _round_half_up(quantile(history, q), 1)
            if len(history) >= minimum_rounds
            else None
        )
    return result
