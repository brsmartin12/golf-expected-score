"""Tests for the typical/potential quantile layer.

Same rule as test_handicap.py: every expected value below was worked out by
hand from the definitions, not captured from a run of the code. A test that
records what the code already does proves only that the code is deterministic.

The quantile definition being asserted throughout is linear interpolation
between order statistics -- the standard one, and the same as numpy's default:

    position = q x (n - 1)
    result   = ordered[floor(position)] + fraction x (next value - this one)
"""

import pytest

from golf.scoring import (
    MINIMUM_ROUNDS,
    NINE_SPREAD_CORRECTION,
    POTENTIAL_QUANTILE,
    TYPICAL_QUANTILE,
    WINDOW,
    Played,
    benchmarks,
    eighteen_from_nine,
    potential_differential,
    quantile,
    score_from_differential,
    typical_differential,
)

# The integers 1..20, used because their quantiles are trivial to verify by
# hand and their spacing makes an interpolated answer obvious when it lands
# between two of them.
ONE_TO_TWENTY = [float(n) for n in range(1, 21)]

# Eight differentials, evenly spaced. Used wherever a list of exactly
# MINIMUM_ROUNDS is wanted.
#   median:        position 0.5 x 7 = 3.5 -> 16 + (18 - 16) x 0.5 = 17.0
#   20th percentile: position 0.2 x 7 = 1.4 -> 12 + (14 - 12) x 0.4 = 12.8
EIGHT = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0]
EIGHT_MEDIAN = 17.0
EIGHT_P20 = 12.8


# ---------------------------------------------------------------------------
# quantile
# ---------------------------------------------------------------------------


def test_median_of_one_to_twenty():
    # position 0.5 x 19 = 9.5, halfway between the 10th and 11th values.
    assert quantile(ONE_TO_TWENTY, 0.5) == pytest.approx(10.5)


def test_twentieth_percentile_of_one_to_twenty():
    # position 0.2 x 19 = 3.8, so 4 + (5 - 4) x 0.8.
    assert quantile(ONE_TO_TWENTY, 0.2) == pytest.approx(4.8)


def test_quantile_at_the_ends_is_the_min_and_max():
    assert quantile(ONE_TO_TWENTY, 0.0) == pytest.approx(1.0)
    assert quantile(ONE_TO_TWENTY, 1.0) == pytest.approx(20.0)


def test_quantile_of_a_single_value_is_that_value():
    """No interpolation is possible, and every quantile of one number is it."""
    assert quantile([14.3], 0.5) == pytest.approx(14.3)
    assert quantile([14.3], 0.2) == pytest.approx(14.3)


def test_quantile_sorts_its_input():
    """Rounds arrive in date order, not score order."""
    shuffled = [20.0, 1.0, 11.0, 5.0]
    # sorted: 1, 5, 11, 20. position 0.5 x 3 = 1.5 -> 5 + (11 - 5) x 0.5 = 8.0
    assert quantile(shuffled, 0.5) == pytest.approx(8.0)


def test_quantile_interpolates_rather_than_picking_a_side():
    # Two values, q = 0.25: position 0.25 x 1 = 0.25 -> 10 + (20 - 10) x 0.25
    assert quantile([10.0, 20.0], 0.25) == pytest.approx(12.5)


def test_quantile_of_an_empty_list_is_an_error():
    with pytest.raises(ValueError, match="empty"):
        quantile([], 0.5)


@pytest.mark.parametrize("bad_q", [-0.1, 1.1, 2.0])
def test_quantile_rejects_a_q_outside_zero_to_one(bad_q):
    with pytest.raises(ValueError, match="between 0 and 1"):
        quantile(ONE_TO_TWENTY, bad_q)


# ---------------------------------------------------------------------------
# typical and potential
# ---------------------------------------------------------------------------


def test_typical_is_the_median():
    assert typical_differential(EIGHT) == pytest.approx(EIGHT_MEDIAN)


def test_potential_is_the_twentieth_percentile():
    assert potential_differential(EIGHT) == pytest.approx(EIGHT_P20)


def test_potential_is_better_than_typical():
    """Lower differential is better, so potential must sit below typical."""
    assert potential_differential(EIGHT) < typical_differential(EIGHT)


def test_the_two_quantiles_are_the_ones_documented():
    """Guard against the constants drifting from what the docs and UI claim."""
    assert TYPICAL_QUANTILE == 0.5
    assert POTENTIAL_QUANTILE == 0.2


def test_results_are_rounded_to_one_decimal_place():
    """Differentials carry one decimal, so the figures drawn from them do too.

    This also scrubs the float noise interpolation leaves behind: the raw
    20th percentile of 1..20 comes out of the arithmetic as 4.800000000000001.
    """
    assert potential_differential(ONE_TO_TWENTY) == 4.8  # exactly, not approx
    assert typical_differential(ONE_TO_TWENTY) == 10.5


def test_too_few_rounds_gives_none_rather_than_a_bad_number():
    """The screen shows a countdown; it must not show a median of three rounds."""
    seven = EIGHT[:-1]
    assert len(seven) == MINIMUM_ROUNDS - 1
    assert typical_differential(seven) is None
    assert potential_differential(seven) is None


def test_exactly_the_minimum_number_of_rounds_is_enough():
    assert len(EIGHT) == MINIMUM_ROUNDS
    assert typical_differential(EIGHT) is not None


def test_no_rounds_at_all_gives_none():
    assert typical_differential([]) is None
    assert potential_differential([]) is None


def test_the_minimum_can_be_lowered_by_the_caller():
    three = [10.0, 20.0, 30.0]
    assert typical_differential(three) is None
    assert typical_differential(three, minimum_rounds=3) == pytest.approx(20.0)


def test_only_the_last_twenty_rounds_count():
    """A 21st round back drops out of the window entirely, however extreme."""
    recent = [10.0] * WINDOW
    assert typical_differential([200.0] + recent) == pytest.approx(10.0)
    assert potential_differential([200.0] + recent) == pytest.approx(10.0)


def test_the_window_takes_the_newest_rounds_not_the_oldest():
    """Differentials arrive oldest-first, so the window is a tail, not a head."""
    old_and_bad = [30.0] * WINDOW
    new_and_good = [10.0] * WINDOW
    assert typical_differential(old_and_bad + new_and_good) == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# score_from_differential
# ---------------------------------------------------------------------------


def test_score_from_differential_baseline():
    # 14.3 x 130/113 + 71.5 = 16.451 + 71.5 = 87.951 -> 88.0
    assert score_from_differential(14.3, 71.5, 130) == pytest.approx(88.0)


def test_score_from_differential_inverts_score_differential():
    """The round trip is the whole reason this function exists."""
    from golf.handicap import score_differential

    differential = score_differential(88, 71.5, 130)
    assert differential == pytest.approx(14.3)
    assert score_from_differential(differential, 71.5, 130) == pytest.approx(88.0)


def test_a_zero_differential_on_a_standard_course_is_the_course_rating():
    assert score_from_differential(0.0, 72.0, 113) == pytest.approx(72.0)


def test_a_harder_slope_turns_the_same_differential_into_a_higher_score():
    easy = score_from_differential(15.0, 70.0, 105)
    hard = score_from_differential(15.0, 70.0, 145)
    assert hard > easy
    # 15 x 105/113 + 70 = 13.938 + 70 = 83.938 -> 83.9
    assert easy == pytest.approx(83.9)
    # 15 x 145/113 + 70 = 19.248 + 70 = 89.248 -> 89.2
    assert hard == pytest.approx(89.2)


def test_pcc_shifts_the_score_stroke_for_stroke():
    """A tough day's PCC of +1 means the same differential took one more shot."""
    plain = score_from_differential(14.3, 71.5, 130)
    adjusted = score_from_differential(14.3, 71.5, 130, pcc=1.0)
    assert adjusted - plain == pytest.approx(1.0)


@pytest.mark.parametrize("bad_slope", [54, 156, 0])
def test_score_from_differential_rejects_an_impossible_slope(bad_slope):
    with pytest.raises(ValueError, match="slope_rating"):
        score_from_differential(14.3, 71.5, bad_slope)


@pytest.mark.parametrize("bad_rating", [0, -1.0])
def test_score_from_differential_rejects_a_non_positive_rating(bad_rating):
    with pytest.raises(ValueError, match="course_rating"):
        score_from_differential(14.3, bad_rating, 130)


# ---------------------------------------------------------------------------
# eighteen_from_nine
# ---------------------------------------------------------------------------


def test_a_nine_exactly_at_the_pivot_converts_to_the_pivot():
    """Half of a golfer's typical, played over nine holes, IS their typical.

    The deviation is zero, so no correction applies and nothing moves. This is
    the fixed point the whole conversion pivots around.
    """
    assert eighteen_from_nine(7.0, 14.0) == pytest.approx(14.0)


def test_the_conversion_sits_between_doubling_and_mean_filling():
    """The two obvious methods bracket it, and it is their geometric mean.

    Doubling 3.0 gives 6.0; filling the missing nine with half a pivot of 4.5
    gives 5.25. sqrt(2) lands at 5.561.
    """
    converted = eighteen_from_nine(3.0, 4.5)

    assert 5.25 < converted < 6.0
    assert converted == pytest.approx(4.5 + 1.5 / NINE_SPREAD_CORRECTION)


def test_the_conversion_scales_spread_by_root_two():
    """The property the whole thing exists for.

    A nine carries half an eighteen's variance. Two nines a stroke apart are
    two eighteens sqrt(2) strokes apart -- not 2 (doubling, too much) and not
    1 (mean-filling, too little).
    """
    pivot = 7.0
    low = eighteen_from_nine(3.0, pivot)
    high = eighteen_from_nine(4.0, pivot)

    assert high - low == pytest.approx(NINE_SPREAD_CORRECTION)


def test_a_good_nine_converts_to_a_good_eighteen():
    """Direction is preserved: lower differential is better, on both scales."""
    pivot = 14.0
    good = eighteen_from_nine(5.0, pivot)   # well under half of 14
    bad = eighteen_from_nine(9.0, pivot)    # well over

    assert good < pivot < bad


# ---------------------------------------------------------------------------
# benchmarks
# ---------------------------------------------------------------------------


def full(differentials):
    """A series of eighteen-hole rounds."""
    return [Played(d) for d in differentials]


def test_benchmarks_returns_one_entry_per_round():
    assert len(benchmarks(full(ONE_TO_TWENTY))) == len(ONE_TO_TWENTY)


def test_benchmarks_are_empty_until_there_is_enough_history():
    """Round i is judged on the i rounds before it, so index 8 is the first."""
    result = benchmarks(full(EIGHT + [26.0, 28.0]))

    assert all(b.typical is None for b in result[:MINIMUM_ROUNDS])
    assert result[MINIMUM_ROUNDS].typical is not None


def test_the_countdown_reaches_zero_exactly_when_the_figures_appear():
    result = benchmarks(full(EIGHT + [26.0]))

    assert [b.rounds_until_benchmarks for b in result[:3]] == [8, 7, 6]
    assert result[MINIMUM_ROUNDS].rounds_until_benchmarks == 0


def test_benchmarks_use_only_the_rounds_before_each_one():
    result = benchmarks(full(EIGHT + [26.0, 28.0]))

    # index 8: history is EIGHT -> median 17.0, 20th percentile 12.8
    assert result[8].typical == pytest.approx(EIGHT_MEDIAN)
    assert result[8].potential == pytest.approx(EIGHT_P20)
    # index 9: history is EIGHT + [26], nine values.
    #   median:    position 0.5 x 8 = 4.0, exactly the 5th value -> 18.0
    #   20th pct:  position 0.2 x 8 = 1.6 -> 12 + (14 - 12) x 0.6 = 13.2
    assert result[9].typical == pytest.approx(18.0)
    assert result[9].potential == pytest.approx(13.2)


def test_a_round_is_never_judged_against_itself():
    """A career round must not raise the bar it is being measured against."""
    assert benchmarks(full(EIGHT + [0.0]))[8].typical == pytest.approx(EIGHT_MEDIAN)


def test_later_rounds_never_change_an_earlier_verdict():
    """Point-in-time correctness, which is what keeps a trend meaningful."""
    short = benchmarks(full(EIGHT + [26.0]))
    long = benchmarks(full(EIGHT + [26.0] + [0.0] * 5))

    assert short[8] == long[8]


def test_the_window_slides_forward():
    """Old rounds fall out of the back as new ones arrive at the front."""
    series = full([1.0, 2.0, 3.0, 100.0, 100.0, 100.0])
    result = benchmarks(series, window=3, minimum_rounds=3)

    assert [b.typical for b in result[:3]] == [None, None, None]
    assert result[3].typical == pytest.approx(2.0)    # history [1, 2, 3]
    assert result[4].typical == pytest.approx(3.0)    # history [2, 3, 100]
    assert result[5].typical == pytest.approx(100.0)  # history [3, 100, 100]


def test_benchmarks_agree_with_the_standalone_quantiles():
    """With no nines in play, this is the same calculation as before."""
    result = benchmarks(full(ONE_TO_TWENTY + [99.0]))[-1]

    assert result.typical == typical_differential(ONE_TO_TWENTY)
    assert result.potential == potential_differential(ONE_TO_TWENTY)


def test_benchmarks_of_an_empty_series_is_empty():
    assert benchmarks([]) == []


# ---------------------------------------------------------------------------
# benchmarks, with nine-hole rounds mixed in
# ---------------------------------------------------------------------------


def test_a_nine_counts_toward_the_minimum_like_any_other_round():
    """Seven eighteens plus a nine is eight rounds, and eight rounds is enough.

    The pivot the conversion needs is a CENTRE, and a doubled nine estimates a
    centre well enough -- so nines carry their own weight here rather than
    waiting on full rounds. Requiring full rounds would leave a golfer who
    mostly plays nine holes with no figure at all.
    """
    seven_and_one = full(EIGHT[:-1]) + [Played(8.0, is_nine=True)]

    assert benchmarks(seven_and_one + [Played(20.0)])[-1].typical is not None
    assert benchmarks(seven_and_one)[-1].rounds_until_benchmarks == 1


def test_a_golfer_who_only_plays_nines_still_gets_both_figures():
    """The case the old full-rounds-only rule shut out entirely."""
    only_nines = [Played(7.0 + 0.4 * i, is_nine=True) for i in range(MINIMUM_ROUNDS)]

    graded = benchmarks(only_nines + [Played(8.0, is_nine=True)])[-1]

    assert graded.typical is not None
    assert graded.potential is not None
    assert graded.potential < graded.typical
    assert graded.rounds_of_history == MINIMUM_ROUNDS


def test_the_pivot_uses_nines_as_well_as_full_rounds():
    """Otherwise the centre would ignore most of a nine-heavy golfer's golf.

    Two windows with the same eighteens but very different nines must produce
    different figures -- the nines are informing the centre, not just riding on
    one derived from the eighteens.
    """
    good_nines = full(EIGHT[:4]) + [Played(4.0, is_nine=True)] * 4
    bad_nines = full(EIGHT[:4]) + [Played(12.0, is_nine=True)] * 4

    assert (
        benchmarks(good_nines + [Played(20.0)])[-1].typical
        < benchmarks(bad_nines + [Played(20.0)])[-1].typical
    )


def test_a_nine_joins_the_population_once_there_is_a_pivot():
    """It counts, and it counts as one round of history."""
    history = full(EIGHT) + [Played(8.5, is_nine=True)]

    graded = benchmarks(history + [Played(20.0)])[-1]

    assert graded.rounds_of_history == 9  # eight eighteens plus the nine


def test_a_nine_moves_typical_the_way_its_quality_deserves():
    """A strong nine pulls typical down; a weak one pushes it up."""
    pivot_only = benchmarks(full(EIGHT) + [Played(20.0)])[-1].typical

    strong = benchmarks(full(EIGHT) + [Played(4.0, is_nine=True), Played(20.0)])[-1]
    weak = benchmarks(full(EIGHT) + [Played(14.0, is_nine=True), Played(20.0)])[-1]

    assert strong.typical < pivot_only < weak.typical


def test_a_nine_is_folded_in_at_its_converted_value():
    """The population is the full rounds plus the converted nine, exactly."""
    nine = Played(6.0, is_nine=True)
    graded = benchmarks(full(EIGHT) + [nine, Played(20.0)])[-1]

    pivot = quantile(EIGHT, TYPICAL_QUANTILE)          # 17.0
    expected = sorted(EIGHT + [eighteen_from_nine(6.0, pivot)])

    assert graded.typical == pytest.approx(
        round(quantile(expected, TYPICAL_QUANTILE), 1)
    )


def test_the_pivot_is_stable_against_its_own_output():
    """The conversion must not calibrate against values it produced.

    The pivot is computed once from the raw window -- full rounds as they are,
    nines doubled -- and then used. There is no feedback loop, so adding copies
    of the same nine moves the median of the population without each copy
    landing somewhere different.
    """
    one = benchmarks(full(EIGHT) + [Played(2.0, is_nine=True), Played(20.0)])[-1]
    four = benchmarks(full(EIGHT) + [Played(2.0, is_nine=True)] * 4 + [Played(20.0)])[-1]

    # More copies of a strong nine pull typical further down, monotonically.
    assert four.typical < one.typical
    assert four.rounds_of_history == one.rounds_of_history + 3


def test_a_nine_can_itself_be_graded():
    """The point of the exercise: a nine gets a verdict like any other round."""
    graded = benchmarks(full(EIGHT) + [Played(7.0, is_nine=True)])[-1]

    assert graded.typical == pytest.approx(EIGHT_MEDIAN)
    assert graded.potential == pytest.approx(EIGHT_P20)
