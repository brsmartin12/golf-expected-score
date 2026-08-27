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
from golf import MINIMUM_ROUNDS
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

# The same tee with its nines rated, both at standard slope and exactly half the
# 18-hole rating -- so a nine's differential is just (score - 36.0).
FLAT_TEE_WITH_NINES = [
    {
        **FLAT_TEE[0],
        "front_course_rating": 36.0,
        "front_slope_rating": 113,
        "back_course_rating": 36.0,
        "back_slope_rating": 113,
    }
]

# Real published figures, USGA course 3035, Blue (M). The two nines differ in
# slope, which is the reason both are stored rather than one shared number.
LOPSIDED_TEE = [
    {
        "name": "Gold", "par": 72, "course_rating": 67.4, "slope_rating": 111,
        "front_course_rating": 33.7, "front_slope_rating": 116,
        "back_course_rating": 33.7, "back_slope_rating": 105,
    }
]


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
# Adding tees to a course that already exists
# ---------------------------------------------------------------------------


def test_a_tee_can_be_added_to_an_existing_course(client):
    """The second set of tees you ever play at a course.

    Courses are unique on name and location and were creatable only with their
    tees attached, so this was unreachable -- you would meet it halfway through
    a backfill with no way past.
    """
    course = add_course(client, tees=FLAT_TEE)

    response = client.post(
        f"/courses/{course['id']}/tees",
        json=[{"name": "White", "par": 72, "course_rating": 69.8, "slope_rating": 124}],
    )

    assert response.status_code == 201
    assert sorted(t["name"] for t in response.json()["tees"]) == ["Blue", "White"]


def test_several_tees_can_be_added_at_once(client):
    course = add_course(client, tees=FLAT_TEE)

    body = client.post(
        f"/courses/{course['id']}/tees",
        json=[
            {"name": "White", "par": 72, "course_rating": 69.8, "slope_rating": 124},
            {"name": "Gold", "par": 72, "course_rating": 67.4, "slope_rating": 111},
        ],
    ).json()

    assert len(body["tees"]) == 3


def test_an_added_tee_keeps_its_nine_hole_ratings(client):
    """Regression guard. The course route once built each Tee from a hand-written
    field list, so the nine-hole columns were accepted and then silently dropped
    before the insert. This route must not repeat that."""
    course = add_course(client, tees=FLAT_TEE)

    body = client.post(
        f"/courses/{course['id']}/tees",
        json=[{
            "name": "Gold", "par": 72, "course_rating": 67.4, "slope_rating": 111,
            "front_course_rating": 33.7, "front_slope_rating": 116,
            "back_course_rating": 33.7, "back_slope_rating": 105,
        }],
    ).json()

    gold = next(t for t in body["tees"] if t["name"] == "Gold")
    assert gold["front_slope_rating"] == 116
    assert gold["back_slope_rating"] == 105


def test_an_added_tee_can_be_played_immediately(client):
    """The whole point: the round that was blocked now goes in."""
    course = add_course(client, tees=FLAT_TEE)
    added = client.post(
        f"/courses/{course['id']}/tees",
        json=[{"name": "White", "par": 72, "course_rating": 69.8, "slope_rating": 124}],
    ).json()
    white = next(t for t in added["tees"] if t["name"] == "White")

    body = log(client, white["id"], "2025-06-14", 88)

    assert body["tee_name"] == "White"
    assert body["score_differential"] == pytest.approx(16.6)  # (88 - 69.8) x 113/124


def test_a_duplicate_tee_name_at_the_same_course_is_rejected(client):
    course = add_course(client, tees=FLAT_TEE)

    response = client.post(f"/courses/{course['id']}/tees", json=FLAT_TEE)

    assert response.status_code == 409
    assert "already has a tee by that name" in response.json()["detail"]


def test_the_same_tee_name_at_a_different_course_is_fine(client):
    """Tee names are unique per course, not globally -- every course has a Blue."""
    other = add_course(client, name="Riverside", tees=FLAT_TEE)

    response = client.post(f"/courses/{other['id']}/tees",
                           json=[{"name": "White", "par": 72,
                                  "course_rating": 69.8, "slope_rating": 124}])

    assert response.status_code == 201


def test_adding_a_tee_to_a_course_that_does_not_exist_is_a_404(client):
    response = client.post("/courses/9999/tees", json=FLAT_TEE)

    assert response.status_code == 404


def test_an_added_tee_cannot_store_half_a_nine(client):
    course = add_course(client, tees=FLAT_TEE)

    response = client.post(
        f"/courses/{course['id']}/tees",
        json=[{"name": "Gold", "par": 72, "course_rating": 67.4,
               "slope_rating": 111, "front_course_rating": 33.7}],
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
    assert body["rounds_until_benchmarks"] == MINIMUM_ROUNDS
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
    assert body["rounds_until_benchmarks"] == 0
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


def test_a_nine_without_nine_hole_ratings_cannot_be_rated(client):
    """Half a round through an 18-hole rating reads several strokes too good.

    Rather than approximate, the round is stored and listed with no differential
    at all -- which is also the prompt to go and enter the tee's nine-hole
    figures.
    """
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])

    body = log(client, tee["id"], "2025-02-01", 41, nine="front")

    assert body["nine"] == "front"
    assert body["score_differential"] is None
    assert body["typical_score"] is None
    assert body["to_typical"] is None


def test_an_unrateable_nine_does_not_disturb_the_benchmarks(client):
    """It is absent from the population, not silently folded in at 41 strokes."""
    tee = add_course(client, tees=FLAT_TEE)["tees"][0]
    log_a_history(client, tee["id"])
    log(client, tee["id"], "2025-02-01", 41, nine="front")

    after = log(client, tee["id"], "2025-02-02", 80)

    assert after["rounds_of_history"] == 8
    assert after["typical_score"] == TYPICAL_AFTER_EIGHT


def test_a_nine_with_ratings_is_graded_against_a_typical_nine(client):
    """The point of the exercise. Scales stay separate: a nine is compared with
    what this golfer usually shoots over nine, not over eighteen."""
    tee = add_course(client, tees=FLAT_TEE_WITH_NINES)["tees"][0]
    log_a_history(client, tee["id"])

    body = log(client, tee["id"], "2025-02-01", 40, nine="front")

    # d9 = 40 - 36.0 = 4.0 on a standard-slope nine.
    assert body["score_differential"] == pytest.approx(4.0)
    # typical differential over eighteen is 4.5, so a typical nine is 2.25,
    # which on this nine is 36.0 + 2.25 = 38.25 -> 38.2 (half up on the tenth).
    assert body["typical_score"] == pytest.approx(38.3)
    assert body["to_typical"] == pytest.approx(1.7)


def test_a_rated_nine_joins_the_population(client):
    """It counts as a round of history, unlike an unrateable one."""
    tee = add_course(client, tees=FLAT_TEE_WITH_NINES)["tees"][0]
    log_a_history(client, tee["id"])
    log(client, tee["id"], "2025-02-01", 40, nine="front")

    after = log(client, tee["id"], "2025-02-02", 80)

    assert after["rounds_of_history"] == 9


def test_a_nine_is_folded_in_with_its_spread_corrected(client):
    """Not doubled -- doubling carries sqrt(2) times too much spread, which
    would drag potential down. See golf/scoring.py."""
    tee = add_course(client, tees=FLAT_TEE_WITH_NINES)["tees"][0]
    log_a_history(client, tee["id"])
    log(client, tee["id"], "2025-02-01", 40, nine="front")  # d9 = 4.0

    after = log(client, tee["id"], "2025-02-02", 80)

    # pivot 4.5; doubled 8.0; corrected 4.5 + 3.5/sqrt(2) = 6.975.
    # Population is 1..8 plus 6.975 -> nine values, median is the 5th = 5.0.
    assert after["typical_score"] == pytest.approx(77.0)  # 5.0 + 72.0


def test_which_nine_was_played_changes_the_rating_used(client):
    """Real tees have lopsided nines -- Gold here is 116 front, 105 back."""
    tee = add_course(client, tees=LOPSIDED_TEE)["tees"][0]

    front = log(client, tee["id"], "2025-03-01", 42, nine="front")
    back = log(client, tee["id"], "2025-03-02", 42, nine="back")

    # Same score, same 33.7 rating, different slope: the harder nine (116)
    # rates the round better, so its differential is lower.
    assert front["score_differential"] < back["score_differential"]
    assert front["score_differential"] == pytest.approx(8.1)   # 8.3 x 113/116
    assert back["score_differential"] == pytest.approx(8.9)    # 8.3 x 113/105


def test_a_nine_cannot_be_logged_with_a_bogus_side(client):
    tee = add_course(client, tees=FLAT_TEE_WITH_NINES)["tees"][0]

    response = client.post(
        "/rounds",
        json={"tee_id": tee["id"], "played_on": "2025-02-01",
              "gross_score": 40, "nine": "middle"},
    )

    assert response.status_code == 422


def test_a_tee_cannot_store_half_a_nine(client):
    """A rating with no slope produces no differential, so it is rejected."""
    response = client.post(
        "/courses",
        json={
            "name": "Half Entered",
            "tees": [{**FLAT_TEE[0], "front_course_rating": 36.0}],
        },
    )

    assert response.status_code == 422


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
