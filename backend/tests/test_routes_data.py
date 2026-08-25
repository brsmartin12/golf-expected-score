"""Tests for the stored-data routes: courses, tees and rounds.

These go through the real app and the real database. Each test gets a
transaction that is rolled back, and the app's session dependency is overridden
to use it -- so a request made inside a test writes through the same transaction
the test can see, and neither leaks into the next one.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.deps import get_current_user
from api.main import app
from db import get_session
from db.models import User
from tests.conftest import requires_database

pytestmark = requires_database


@pytest.fixture
def client(db_session):
    """A TestClient wired to the test's transaction.

    dependency_overrides is FastAPI's seam for exactly this: swap what a
    Depends() resolves to without touching the routes. Both the session and the
    current user are overridden, the latter because get_current_user commits,
    which would break the rollback isolation.
    """
    user = User(email="test@localhost", display_name="Test Golfer")
    db_session.add(user)
    db_session.flush()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()


def add_course(client, name="Pine Hills", tees=None):
    payload = {
        "name": name,
        "city": "Austin",
        "state": "TX",
        "tees": tees
        or [{"name": "Blue", "par": 72, "course_rating": 71.5, "slope_rating": 130}],
    }
    response = client.post("/courses", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


def test_a_course_is_created_with_its_tees(client):
    course = add_course(
        client,
        tees=[
            {"name": "Blue", "par": 72, "course_rating": 71.5, "slope_rating": 130},
            {"name": "White", "par": 72, "course_rating": 69.8, "slope_rating": 124},
        ],
    )

    assert {t["name"] for t in course["tees"]} == {"Blue", "White"}
    assert course["tees"][0]["course_rating"] == 71.5  # a number, not "71.5"


def test_a_course_must_have_at_least_one_tee(client):
    """A course with no tees can answer no question this app asks."""
    response = client.post("/courses", json={"name": "Empty", "tees": []})

    assert response.status_code == 422


def test_a_duplicate_course_is_a_conflict_not_a_crash(client):
    add_course(client)
    response = client.post(
        "/courses",
        json={
            "name": "Pine Hills",
            "city": "Austin",
            "state": "TX",
            "tees": [
                {"name": "Blue", "par": 72, "course_rating": 71.5, "slope_rating": 130}
            ],
        },
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_courses_list_includes_their_tees(client):
    add_course(client, name="Riverside")
    add_course(client, name="Pine Hills")

    listed = client.get("/courses").json()

    assert [c["name"] for c in listed] == ["Pine Hills", "Riverside"]  # alphabetical
    assert all(c["tees"] for c in listed)


def test_a_tee_with_an_illegal_slope_is_rejected(client):
    response = client.post(
        "/courses",
        json={
            "name": "Impossible",
            "tees": [
                {"name": "Blue", "par": 72, "course_rating": 71.5, "slope_rating": 999}
            ],
        },
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Rounds
# ---------------------------------------------------------------------------


def test_logging_a_round_returns_the_verdict_in_the_same_response(client):
    """The post-round moment is one request, not a save followed by a fetch."""
    tee = add_course(client)["tees"][0]

    response = client.post(
        "/rounds",
        json={
            "tee_id": tee["id"],
            "played_on": "2025-06-14",
            "gross_score": 88,
            "index_at_time": 10.0,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["score_differential"] == 14.3
    assert body["potential_score"] == 83.0
    assert body["strokes_vs_potential"] == -5.0
    assert body["to_potential"] == 5.0  # over, and over is worse
    assert body["course_name"] == "Pine Hills"
    assert body["tee_name"] == "Blue"


def test_a_round_without_an_index_still_gets_a_differential(client):
    """The backfill case. The differential needs no index; the rest does."""
    tee = add_course(client)["tees"][0]

    body = client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2023-04-02", "gross_score": 88},
    ).json()

    assert body["score_differential"] == 14.3
    assert body["index_at_time"] is None
    assert body["potential_score"] is None
    assert body["strokes_vs_potential"] is None
    assert body["to_potential"] is None


def test_pcc_reaches_the_differential(client):
    tee = add_course(client)["tees"][0]

    plain = client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2025-06-14", "gross_score": 88},
    ).json()
    tough = client.post(
        "/rounds",
        json={
            "tee_id": tee["id"],
            "played_on": "2025-06-15",
            "gross_score": 88,
            "pcc": 1,
        },
    ).json()

    assert tough["score_differential"] < plain["score_differential"]


def test_rounds_come_back_most_recently_played_first(client):
    """Ordered by when they were PLAYED, not when they were entered -- a
    backfill enters the oldest rounds last."""
    tee = add_course(client)["tees"][0]
    for played_on in ["2025-06-14", "2023-04-02", "2024-09-30"]:
        client.post(
            "/rounds",
            json={"tee_id": tee["id"], "played_on": played_on, "gross_score": 88},
        )

    listed = client.get("/rounds").json()

    assert [r["played_on"] for r in listed] == ["2025-06-14", "2024-09-30", "2023-04-02"]


def test_a_round_on_an_unknown_tee_is_a_404(client):
    response = client.post(
        "/rounds",
        json={"tee_id": 9999, "played_on": "2025-06-14", "gross_score": 88},
    )

    assert response.status_code == 404


def test_an_impossible_score_is_rejected(client):
    tee = add_course(client)["tees"][0]

    response = client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2025-06-14", "gross_score": 0},
    )

    assert response.status_code == 422


def test_a_round_can_be_dated_in_the_past(client):
    """Backfilled history keeps its original date, which is the whole point of
    played_on being supplied rather than defaulted to today."""
    tee = add_course(client)["tees"][0]

    body = client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2021-08-03", "gross_score": 94},
    ).json()

    assert body["played_on"] == "2021-08-03"
    assert date.fromisoformat(body["played_on"]) < date.today()


def test_one_golfer_does_not_see_another_golfers_rounds(client, db_session):
    """user_id is in the schema before auth exists precisely so this holds from
    the start rather than being retrofitted."""
    tee = add_course(client)["tees"][0]
    client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2025-06-14", "gross_score": 88},
    )

    stranger = User(email="other@localhost", display_name="Someone Else")
    db_session.add(stranger)
    db_session.flush()
    app.dependency_overrides[get_current_user] = lambda: stranger

    assert client.get("/rounds").json() == []
