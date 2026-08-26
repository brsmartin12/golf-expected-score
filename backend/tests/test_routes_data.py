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


# A slope-113 course rated at exactly 72.0, which makes every expected value
# below checkable in your head: on a standard-slope tee the differential formula
# collapses to (score - course rating), so a 76 rates 4.0 and nothing else.
FLAT_TEE = [{"name": "Blue", "par": 72, "course_rating": 72.0, "slope_rating": 113}]


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


def log(client, tee_id, played_on, gross_score, **extra):
    response = client.post(
        "/rounds",
        json={
            "tee_id": tee_id,
            "played_on": played_on,
            "gross_score": gross_score,
            **extra,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def log_a_history(client, tee_id, scores=range(73, 81)):
    """Eight rounds on the flat tee, one per day from 2025-01-01.

    Scores 73..80 on a 72.0/113 tee give differentials 1.0..8.0, whose
    quantiles are worked out by hand as:

        median (typical)        position 0.5 x 7 = 3.5 -> 4 + 0.5 = 4.5
        20th percentile (potential)  position 0.2 x 7 = 1.4 -> 2 + 0.4 = 2.4

    Back on this tee that is a typical of 76.5 and a potential of 74.4.
    """
    for day, score in enumerate(scores, start=1):
        log(client, tee_id, f"2025-01-{day:02d}", score)


TYPICAL_AFTER_EIGHT = 76.5
POTENTIAL_AFTER_EIGHT = 74.4


def test_the_first_round_has_a_differential_but_no_benchmarks(client):
    """Nothing to compare it to yet, so the app says so instead of guessing."""
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]

    body = log(client, tee["id"], "2025-06-14", 88)

    assert body["score_differential"] == 16.0  # 88 - 72.0, slope 113
    assert body["rounds_of_history"] == 0
    assert body["typical_score"] is None
    assert body["potential_score"] is None
    assert body["to_typical"] is None
    assert body["to_potential"] is None


def test_logging_a_round_returns_the_verdict_in_the_same_response(client):
    """The post-round moment is one request, not a save followed by a fetch."""
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])

    response = client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2025-02-01", "gross_score": 80},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["rounds_of_history"] == 8
    assert body["typical_score"] == TYPICAL_AFTER_EIGHT
    assert body["potential_score"] == POTENTIAL_AFTER_EIGHT
    assert body["to_typical"] == 3.5  # 80 - 76.5, over and over is worse
    assert body["to_potential"] == 5.6  # 80 - 74.4
    assert body["course_name"] == "Pine Hills"
    assert body["tee_name"] == "Blue"


def test_beating_your_typical_reads_as_a_negative_number(client):
    """The display convention: a minus sign means better, everywhere a golfer
    can see it. See ROADMAP.md."""
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])

    body = log(client, tee["id"], "2025-02-01", 74)

    assert body["to_typical"] == -2.5  # 74 - 76.5
    assert body["to_potential"] == -0.4  # 74 - 74.4, better than his own best form


def test_a_round_is_graded_on_the_rounds_before_it_and_never_on_later_ones(client):
    """Point-in-time correctness, which is what keeps a trend meaningful.

    Grading the whole history against today's numbers would rewrite every past
    round each time a score is logged.
    """
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])
    graded = log(client, tee["id"], "2025-02-01", 80)

    # A run of much better golf afterwards must not touch that verdict.
    for day in range(2, 8):
        log(client, tee["id"], f"2025-02-{day:02d}", 68)

    unchanged = next(r for r in client.get("/rounds").json() if r["id"] == graded["id"])
    assert unchanged["typical_score"] == TYPICAL_AFTER_EIGHT
    assert unchanged["to_typical"] == 3.5


def test_a_backfilled_round_is_graded_on_its_own_date(client):
    """A round entered last but played first has no history behind it, and it
    becomes history for everything that follows."""
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])
    later = log(client, tee["id"], "2025-02-01", 80)

    backfilled = log(client, tee["id"], "2024-05-05", 85)

    assert backfilled["rounds_of_history"] == 0
    regraded = next(r for r in client.get("/rounds").json() if r["id"] == later["id"])
    assert regraded["rounds_of_history"] == 9


def test_nine_hole_rounds_are_kept_out_of_the_benchmarks(client):
    """Half a round through an 18-hole rating produces a differential several
    strokes too low, which would drag both figures down for twenty rounds."""
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])

    nine = log(client, tee["id"], "2025-02-01", 41, is_nine_hole=True)
    assert nine["typical_score"] is None
    assert nine["rounds_of_history"] == 0

    after = log(client, tee["id"], "2025-02-02", 80)
    assert after["rounds_of_history"] == 8  # the nine did not count
    assert after["typical_score"] == TYPICAL_AFTER_EIGHT


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
