"""Tests for the HTTP layer.

These do NOT re-test the golf math -- test_handicap.py already proves those
formulas against hand-worked values. What is under test here is the wiring:
does a JSON request reach the right function, do the numbers come back in the
right fields, and does bad input fail in a useful way?

TestClient calls the app directly, in-process. No server starts, no port is
bound, nothing is sent over a socket -- which is why these run in milliseconds
and need no cleanup.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import app, value_error_handler

client = TestClient(app)

# The same baseline as test_handicap.py, so the expected values below are the
# ones already verified by hand there:
#   10.0 x 130/113 = 11.504 strokes
#   potential score: 11.504 + 71.5        = 83.004 -> 83.0
#   course handicap: 11.504 + (71.5 - 72) = 11.004 -> 11
BASELINE = {
    "handicap_index": 10.0,
    "slope_rating": 130,
    "course_rating": 71.5,
}


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


def test_health_reports_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_generated():
    """The /docs page is rendered from this schema, so if it builds, /docs works."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/potential-score" in response.json()["paths"]


# ---------------------------------------------------------------------------
# /potential-score
# ---------------------------------------------------------------------------


def test_potential_score_returns_the_hand_worked_value():
    response = client.post("/potential-score", json={**BASELINE, "par": 72})

    assert response.status_code == 200
    assert response.json()["potential_score"] == 83.0


def test_potential_score_includes_course_handicap_when_par_is_given():
    response = client.post("/potential-score", json={**BASELINE, "par": 72})
    body = response.json()

    assert body["course_handicap"] == 11
    assert body["par_plus_course_handicap"] == 83


def test_par_dependent_fields_are_null_without_par():
    """Rather than defaulting par to 72 and quietly returning a wrong number."""
    response = client.post("/potential-score", json=BASELINE)
    body = response.json()

    assert response.status_code == 200
    assert body["potential_score"] == 83.0
    assert body["course_handicap"] is None
    assert body["par_plus_course_handicap"] is None


# ---------------------------------------------------------------------------
# /round
# ---------------------------------------------------------------------------


def test_round_grades_a_score_against_potential():
    response = client.post("/round", json={**BASELINE, "score": 88})
    body = response.json()

    assert response.status_code == 200
    assert body["potential_score"] == 83.0
    assert body["strokes_vs_potential"] == -5.0  # five worse than potential
    assert body["score_differential"] == 14.3
    assert body["beat_potential"] is False


def test_beating_your_potential_sets_the_flag():
    response = client.post("/round", json={**BASELINE, "score": 79})
    body = response.json()

    assert body["strokes_vs_potential"] == 4.0
    assert body["beat_potential"] is True


# ---------------------------------------------------------------------------
# The two orientations of the same gap
# ---------------------------------------------------------------------------
# strokes_vs_potential is for analysis (higher is better). to_potential is for
# display, in golf's to-par orientation (positive is over, and worse). Getting
# these backwards in the UI would tell a golfer a bad round was a good one.


def test_a_worse_round_is_over_potential():
    body = client.post("/round", json={**BASELINE, "score": 88}).json()

    assert body["to_potential"] == 5.0  # five OVER, the way a card reads
    assert body["strokes_vs_potential"] == -5.0


def test_a_better_round_is_under_potential():
    body = client.post("/round", json={**BASELINE, "score": 79}).json()

    assert body["to_potential"] == -4.0  # four UNDER
    assert body["strokes_vs_potential"] == 4.0


@pytest.mark.parametrize("score", [70, 79, 83, 88, 101])
def test_the_two_orientations_are_always_exact_negatives(score):
    """Never recomputed independently, so rounding cannot drift them apart."""
    body = client.post("/round", json={**BASELINE, "score": score}).json()

    assert body["to_potential"] == -body["strokes_vs_potential"]


def test_pcc_defaults_to_zero_when_omitted():
    with_default = client.post("/round", json={**BASELINE, "score": 88}).json()
    explicit_zero = client.post(
        "/round", json={**BASELINE, "score": 88, "pcc": 0.0}
    ).json()

    assert with_default == explicit_zero


def test_pcc_shifts_the_differential():
    """Harder conditions (positive PCC) make the same score rate better."""
    baseline = client.post("/round", json={**BASELINE, "score": 88}).json()
    tough_day = client.post("/round", json={**BASELINE, "score": 88, "pcc": 1.0}).json()

    assert tough_day["score_differential"] < baseline["score_differential"]


# ---------------------------------------------------------------------------
# Validation at the HTTP boundary
# ---------------------------------------------------------------------------
# 422 Unprocessable Entity is FastAPI's status for "well-formed request, but the
# contents don't satisfy the schema". Distinct from 400 (malformed) and from 500
# (the server itself broke).


@pytest.mark.parametrize("bad_slope", [54, 156, 0, -10])
def test_slope_outside_the_legal_range_is_rejected(bad_slope):
    response = client.post(
        "/potential-score", json={**BASELINE, "slope_rating": bad_slope}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("boundary_slope", [55, 155])
def test_slope_boundaries_are_accepted(boundary_slope):
    response = client.post(
        "/potential-score", json={**BASELINE, "slope_rating": boundary_slope}
    )

    assert response.status_code == 200


def test_non_numeric_input_is_rejected():
    response = client.post(
        "/potential-score", json={**BASELINE, "slope_rating": "banana"}
    )

    assert response.status_code == 422


def test_missing_required_field_is_rejected():
    response = client.post("/potential-score", json={"handicap_index": 10.0})

    assert response.status_code == 422
    # The error names the fields that were missing, which is what makes a 422
    # actionable for whoever is calling the API.
    missing = {tuple(err["loc"]) for err in response.json()["detail"]}
    assert ("body", "slope_rating") in missing
    assert ("body", "course_rating") in missing


def test_negative_course_rating_is_rejected():
    response = client.post("/potential-score", json={**BASELINE, "course_rating": -1})

    assert response.status_code == 422


def test_value_error_from_the_math_layer_becomes_a_422_not_a_500():
    """The safety net for a gap between Pydantic's bounds and handicap.py's.

    Built on a throwaway app rather than the real one: registering a route that
    deliberately explodes onto the shared `app` would leak into every other test
    in the file (and into the OpenAPI schema asserted on above).
    """
    doomed = FastAPI()
    doomed.add_exception_handler(ValueError, value_error_handler)

    @doomed.get("/boom")
    def boom():
        raise ValueError("slope_rating must be between 55 and 155, got 999")

    # raise_server_exceptions=False lets the handler's response through instead
    # of re-raising the exception into the test.
    response = TestClient(doomed, raise_server_exceptions=False).get("/boom")

    assert response.status_code == 422
    assert response.json()["detail"] == "slope_rating must be between 55 and 155, got 999"
