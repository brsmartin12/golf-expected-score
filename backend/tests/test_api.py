"""Tests for the HTTP layer.

These do NOT re-test the golf math -- test_handicap.py and test_scoring.py
already prove those formulas against hand-worked values. What is under test here
is the wiring: does the app build, do the schemas enforce their bounds, and does
bad input fail in a useful way?

TestClient calls the app directly, in-process. No server starts, no port is
bound, nothing is sent over a socket -- which is why these run in milliseconds
and need no cleanup.

Nothing here touches the database, so it all runs on a fresh clone with no
Postgres. The routes that do need one are tested in test_routes_data.py, which
skips when no database is reachable.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app, value_error_handler
from api.schemas import RoundCreate, TeeCreate
from golf.handicap import MAX_SLOPE, MIN_SLOPE

client = TestClient(app)

TEE = {"name": "Blue", "par": 72, "course_rating": 71.5, "slope_rating": 130}


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
    assert "/rounds" in response.json()["paths"]


def test_there_is_no_calculator_endpoint():
    """Regression guard on a deliberate removal.

    POST /potential-score took a Handicap Index and returned a score. It went
    when the app stopped computing an index -- see the module docstring in
    golf/handicap.py. The USGA already ships that calculator; the numbers this
    app shows come from a golfer's own rounds and hang off /rounds.
    """
    paths = client.get("/openapi.json").json()["paths"]

    assert "/potential-score" not in paths
    assert "/round" not in paths


def test_no_request_or_response_takes_a_handicap_index():
    """Nothing in the published contract mentions one, in any spelling."""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    fields = {name for model in schemas.values() for name in model.get("properties", {})}

    assert not [f for f in fields if "handicap" in f or "index" in f]


# ---------------------------------------------------------------------------
# Validation at the schema boundary
# ---------------------------------------------------------------------------
# Pydantic rejects bad input before a route function runs, which is what turns a
# malformed request into a clean 422 instead of an exception from the math.
# These call the models directly: the bounds are the thing under test, and going
# through HTTP would drag a database in for no extra coverage.


@pytest.mark.parametrize("bad_slope", [54, 156, 0, -10])
def test_slope_outside_the_legal_range_is_rejected(bad_slope):
    with pytest.raises(ValidationError):
        TeeCreate(**{**TEE, "slope_rating": bad_slope})


@pytest.mark.parametrize("boundary_slope", [MIN_SLOPE, MAX_SLOPE])
def test_slope_boundaries_are_accepted(boundary_slope):
    """55 and 155 are legal; the bounds are inclusive, and they are imported
    from golf.handicap rather than retyped, so the two layers cannot drift."""
    assert TeeCreate(**{**TEE, "slope_rating": boundary_slope}).slope_rating == boundary_slope


def test_non_numeric_input_is_rejected():
    with pytest.raises(ValidationError):
        TeeCreate(**{**TEE, "slope_rating": "banana"})


def test_negative_course_rating_is_rejected():
    with pytest.raises(ValidationError):
        TeeCreate(**{**TEE, "course_rating": -1})


def test_missing_required_field_is_reported_by_name():
    """What makes a 422 actionable for whoever is calling the API."""
    with pytest.raises(ValidationError) as caught:
        RoundCreate(tee_id=1)

    missing = {error["loc"] for error in caught.value.errors()}
    assert ("played_on",) in missing
    assert ("gross_score",) in missing


def test_an_impossible_score_is_rejected():
    with pytest.raises(ValidationError):
        RoundCreate(tee_id=1, played_on="2025-06-14", gross_score=0)


# ---------------------------------------------------------------------------
# The safety net under the schemas
# ---------------------------------------------------------------------------


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
