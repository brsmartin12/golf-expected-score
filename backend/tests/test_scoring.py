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
    POTENTIAL_QUANTILE,
    TYPICAL_QUANTILE,
    WINDOW,
    potential_differential,
    quantile,
    score_from_differential,
    trailing,
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
# trailing
# ---------------------------------------------------------------------------


def test_trailing_returns_one_entry_per_round():
    assert len(trailing(ONE_TO_TWENTY, 0.5)) == len(ONE_TO_TWENTY)


def test_trailing_is_none_until_there_is_enough_history():
    """Round i is judged on the i rounds before it, so index 8 is the first."""
    ten = EIGHT + [26.0, 28.0]
    result = trailing(ten, 0.5)
    assert result[:MINIMUM_ROUNDS] == [None] * MINIMUM_ROUNDS
    assert result[MINIMUM_ROUNDS] is not None


def test_trailing_uses_only_the_rounds_before_each_one():
    ten = EIGHT + [26.0, 28.0]
    result = trailing(ten, 0.5)
    # index 8: history is EIGHT -> median 17.0 (see EIGHT_MEDIAN above)
    assert result[8] == pytest.approx(EIGHT_MEDIAN)
    # index 9: history is EIGHT + [26], nine values.
    #   position 0.5 x 8 = 4.0, exactly the 5th value -> 18.0
    assert result[9] == pytest.approx(18.0)


def test_trailing_at_the_twentieth_percentile():
    ten = EIGHT + [26.0, 28.0]
    result = trailing(ten, 0.2)
    assert result[8] == pytest.approx(EIGHT_P20)
    # index 9: nine values, position 0.2 x 8 = 1.6 -> 12 + (14 - 12) x 0.6 = 13.2
    assert result[9] == pytest.approx(13.2)


def test_a_round_is_never_judged_against_itself():
    """Position i must not see differentials[i]; a career round must not raise
    the bar it is being measured against."""
    nine = EIGHT + [0.0]
    assert trailing(nine, 0.5)[8] == pytest.approx(EIGHT_MEDIAN)


def test_trailing_window_slides_forward():
    """Old rounds fall out of the back as new ones arrive at the front."""
    series = [1.0, 2.0, 3.0, 100.0, 100.0, 100.0]
    result = trailing(series, 0.5, window=3, minimum_rounds=3)
    assert result[:3] == [None, None, None]
    assert result[3] == pytest.approx(2.0)    # history [1, 2, 3]
    assert result[4] == pytest.approx(3.0)    # history [2, 3, 100]
    assert result[5] == pytest.approx(100.0)  # history [3, 100, 100]


def test_trailing_agrees_with_the_standalone_quantiles():
    """The point-in-time figure at the end of the list is the current figure."""
    history = ONE_TO_TWENTY
    # Appending a round makes the whole of `history` its trailing window.
    assert trailing(history + [99.0], TYPICAL_QUANTILE)[-1] == typical_differential(history)
    assert trailing(history + [99.0], POTENTIAL_QUANTILE)[-1] == potential_differential(history)


def test_trailing_of_an_empty_history_is_empty():
    assert trailing([], 0.5) == []
