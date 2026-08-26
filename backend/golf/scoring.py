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

Nine-hole rounds
----------------
A nine is half a round, and folding one into a quantile is not as simple as
doubling it. Doubling doubles the noise along with the signal: a nine carries
half an eighteen's variance, so a doubled nine has sqrt(2) times too MUCH
spread. The WHS's own method -- fill the missing nine with the player's expected
score -- has the opposite problem, because imputing a mean adds no variance at
all, leaving sqrt(2) times too LITTLE.

Neither error is harmless here. Typical is a median and survives both, but
potential is a 20th percentile, and a percentile moves with the spread of the
population it is drawn from: too much spread flatters your potential, too little
understates it. Simulated over 8,000 golfers, doubling pulls potential 0.23
strokes low at a 50% nine share and mean-filling pushes it 0.53 high.

Writing both as "centre + deviation x multiplier" shows the fix. Doubling uses
2, mean-filling uses 1, and the multiplier that reproduces a real eighteen's
spread is their geometric mean:

    contributed = typical + (2 x nine_differential - typical) / sqrt(2)

That is `eighteen_from_nine` below. It leaves potential's bias at +0.18 -- the
same figure you get with no nine-hole rounds at all, which is small-sample bias
in the estimator rather than anything the conversion introduced.

The catch is upstream, in the ratings. A nine needs its OWN Course Rating and
Slope Rating, which the USGA publishes per tee. Halving the 18-hole rating is
accurate to about 0.13 strokes, but the slope genuinely differs between the two
nines -- 116 front against 105 back is a real published example -- and using the
18-hole slope costs up to 0.87 strokes, four times what the conversion gains. So
a nine only joins the population when its tee has real nine-hole figures stored.

What the numbers may NOT be used for
------------------------------------
Allocating strokes between players. Because this app takes gross scores while
the WHS caps every hole at net double bogey, a golfer's figure here is inflated
in proportion to how often they blow up — two players a handicap system would
rate a quarter of a stroke apart can come out over two strokes apart here. That
cancels in every self-referential comparison (typical against potential, this
course against your overall) and does not cancel between people. See ROADMAP.md.
"""

from typing import NamedTuple

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

# A nine holds half an eighteen's variance, so doubling one overshoots the real
# spread by exactly sqrt(2). See "Nine-hole rounds" in the module docstring.
NINE_SPREAD_CORRECTION = 2 ** 0.5


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


class Played(NamedTuple):
    """One round in a chronological series, as the quantile layer sees it.

    `differential` is on the scale its own ratings produce: the 18-hole scale
    for a full round, the nine-hole scale for a nine. Mixing them is the whole
    problem `benchmarks` exists to solve, so the flag travels with the number
    rather than being inferred from its size.

    `is_nine` False with no nine-hole ratings available is how a nine that
    cannot be converted is passed in -- see `benchmarks`. Such a round should
    simply be left out of the series instead.
    """

    differential: float
    is_nine: bool = False


class Benchmark(NamedTuple):
    """What a golfer's history says about one round, before that round is seen.

    Both figures are on the 18-hole scale and are None until there is enough
    history. `rounds_until_benchmarks` counts down to that; it reaches 0 at the
    same moment the figures appear.
    """

    typical: float | None
    potential: float | None
    rounds_of_history: int
    rounds_until_benchmarks: int


def eighteen_from_nine(nine_differential: float, typical_differential: float) -> float:
    """Put a nine-hole differential onto the 18-hole scale, spread and all.

    Doubling would get the centre right and the spread wrong by sqrt(2); so
    would filling the missing nine with the player's mean, in the other
    direction. This keeps the centre and corrects the spread, which is what a
    percentile needs -- see "Nine-hole rounds" in the module docstring.

    `typical_differential` is the golfer's own median, on the 18-hole scale, and
    it must come from rounds played BEFORE this one. It is the pivot the
    deviation is measured from, so a wrong one shifts the result.
    """
    doubled = 2 * nine_differential
    deviation = doubled - typical_differential
    return typical_differential + deviation / NINE_SPREAD_CORRECTION


def benchmarks(
    rounds: list[Played],
    window: int = WINDOW,
    minimum_rounds: int = MINIMUM_ROUNDS,
) -> list[Benchmark]:
    """For each round, what the rounds BEFORE it say the golfer usually shoots.

    Oldest first, one Benchmark per round. Position i sees at most `window`
    rounds ending at i-1, so a round is never judged against itself or against
    rounds that had not been played yet. Computing a golfer's whole history
    against today's numbers silently rewrites every past round and destroys
    every trend; this is the discipline that prevents it.

    Nines are folded in through `eighteen_from_nine`, which needs a typical to
    pivot on -- so the minimum applies to the FULL rounds in the window, not to
    the entry count. A golfer with seven eighteens and nine nines still has no
    benchmark: there is nothing to calibrate the conversion against, and no
    amount of nines supplies it. That is a real limit, not an oversight.
    """
    result: list[Benchmark] = []

    for i in range(len(rounds)):
        history = rounds[max(0, i - window) : i]
        full = [r.differential for r in history if not r.is_nine]

        if len(full) < minimum_rounds:
            result.append(
                Benchmark(None, None, 0, max(0, minimum_rounds - len(full)))
            )
            continue

        # The pivot: this golfer's median over the full rounds alone. Drawn from
        # the same window, so it moves with them rather than lagging behind.
        pivot = quantile(full, TYPICAL_QUANTILE)
        population = full + [
            eighteen_from_nine(r.differential, pivot)
            for r in history
            if r.is_nine
        ]

        result.append(
            Benchmark(
                typical=_round_half_up(quantile(population, TYPICAL_QUANTILE), 1),
                potential=_round_half_up(quantile(population, POTENTIAL_QUANTILE), 1),
                rounds_of_history=len(population),
                rounds_until_benchmarks=0,
            )
        )

    return result
