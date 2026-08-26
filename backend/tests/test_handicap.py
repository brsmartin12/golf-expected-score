"""Tests for the single-round handicap math.

Every expected value below was worked out by hand from the WHS formulas, not
generated from the code -- otherwise the tests would only prove the code agrees
with itself.

Notes on pytest idioms used here:
  - Files named test_*.py with functions named test_* are collected automatically.
  - Plain `assert` is enough; pytest rewrites it to show both sides on failure.
  - pytest.approx compares floats with a tolerance, because 0.1 + 0.2 != 0.3 in
    binary floating point.
  - @pytest.mark.parametrize runs the same test body over several inputs, each
    reported as a separate test.

Typical and potential are no longer here. They are quantiles of a scoring
record rather than functions of an index -- see tests/test_scoring.py.
"""

import pytest

from golf.handicap import (
    _round_half_up,
    course_handicap,
    playing_handicap,
    score_differential,
)

# A representative course: moderately hard tee.
COURSE = dict(course_rating=71.5, slope_rating=130)
PAR = 72


# ---------------------------------------------------------------------------
# Score differential -- the app's actual purpose
# ---------------------------------------------------------------------------


def test_score_differential_baseline():
    # (88 - 71.5) x 113/130 = 14.342 -> 14.3
    assert score_differential(88, 71.5, 130) == pytest.approx(14.3)


def test_the_whole_point_same_score_different_courses():
    """An 88 is a very different round depending on where it was shot.

    This is the app's thesis: on a brutal course an 88 rates 10.5 (a strong
    round), while on an easy one the same 88 rates 19.0.
    """
    on_a_monster = score_differential(88, 74.5, 145)
    on_a_pushover = score_differential(88, 69.0, 113)

    assert on_a_monster == pytest.approx(10.5)
    assert on_a_pushover == pytest.approx(19.0)
    assert on_a_monster < on_a_pushover


def test_shooting_the_course_rating_on_a_standard_course_rates_zero():
    assert score_differential(72, 72.0, 113) == pytest.approx(0.0)


def test_pcc_adjusts_the_differential():
    """A positive PCC means conditions were hard, so the same score rates better."""
    without_pcc = score_differential(88, 71.5, 130)
    with_pcc = score_differential(88, 71.5, 130, pcc=1.0)
    assert with_pcc < without_pcc


# ---------------------------------------------------------------------------
# Course handicap
#
# These take an OFFICIAL, externally-issued index -- they exist for the net
# match calculator, not for anything the app computes about you.
# ---------------------------------------------------------------------------


def test_course_handicap_baseline():
    # 10.0 x 130/113 = 11.504, + (71.5 - 72) = 11.004 -> 11
    assert course_handicap(10.0, **COURSE, par=PAR) == 11


def test_scratch_golfer_on_a_standard_course_gets_no_strokes():
    assert course_handicap(0.0, 113, 72.0, 72) == 0


def test_a_harder_tee_gives_more_strokes():
    assert course_handicap(18.0, 145, 74.5, 72) > course_handicap(18.0, 105, 68.0, 72)


# ---------------------------------------------------------------------------
# Rounding
# ---------------------------------------------------------------------------


def test_course_handicap_rounds_half_up_not_to_even():
    """Regression test for Python's banker's rounding.

    On a slope-113 course where CR == Par, the course handicap is just the
    index: 10.5. WHS rounds that up to 11. The built-in round() would return
    10, because it rounds halves to the nearest EVEN number. This test fails
    if _round_half_up is ever swapped for round().
    """
    assert course_handicap(10.5, 113, 72.0, 72) == 11
    assert round(10.5) == 10  # documents the behaviour being avoided


@pytest.mark.parametrize(
    "value,expected",
    [(0.5, 1), (1.5, 2), (2.5, 3), (10.5, 11), (-0.5, -1), (-1.5, -2)],
)
def test_round_half_up_goes_away_from_zero(value, expected):
    assert _round_half_up(value) == expected


# ---------------------------------------------------------------------------
# Playing handicap
# ---------------------------------------------------------------------------


def test_playing_handicap_default_is_full_handicap():
    assert playing_handicap(12) == 12


@pytest.mark.parametrize(
    "course_hcp,allowance,expected",
    [
        (12, 0.95, 11),  # 11.4  -> 11   individual stroke play
        (12, 0.85, 10),  # 10.2  -> 10   four-ball
        (20, 0.95, 19),  # 19.0  -> 19
        (10, 0.95, 10),  # 9.5   -> 10   half rounds up
    ],
)
def test_playing_handicap_applies_allowance(course_hcp, allowance, expected):
    assert playing_handicap(course_hcp, allowance) == expected


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_slope", [0, 54, 156, 200, -10])
def test_slope_outside_the_legal_range_is_rejected(bad_slope):
    with pytest.raises(ValueError, match="slope_rating"):
        score_differential(88, 71.5, bad_slope)


@pytest.mark.parametrize("bad_rating", [0, -1.0])
def test_non_positive_course_rating_is_rejected(bad_rating):
    with pytest.raises(ValueError, match="course_rating"):
        score_differential(88, bad_rating, 130)


def test_non_positive_par_is_rejected():
    with pytest.raises(ValueError, match="par"):
        course_handicap(10.0, 130, 71.5, 0)


def test_negative_allowance_is_rejected():
    with pytest.raises(ValueError, match="allowance"):
        playing_handicap(12, -0.5)


def test_slope_boundaries_are_allowed():
    """55 and 155 are legal; the check is inclusive."""
    assert score_differential(88, 71.5, 55) > 0
    assert score_differential(88, 71.5, 155) > 0
