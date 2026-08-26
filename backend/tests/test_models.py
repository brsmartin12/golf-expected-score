"""Tests for the ORM models.

These run against real Postgres, not a stand-in, because most of what is worth
testing here is enforced by the database: CHECK constraints, unique constraints,
foreign keys and cascade deletes. An in-memory SQLite would let several of these
tests pass while the real schema was wrong.

Every test gets a transaction that is rolled back afterwards (see `db_session`
in conftest.py), so they cannot leak rows into one another.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from db.models import Course, Round, Tee, User
from golf import score_differential, score_from_differential
from tests.conftest import requires_database

pytestmark = requires_database


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# These helpers flush, so the row exists before the test body continues. A test
# that expects a constraint to fire must therefore construct the offending row
# itself, inside the pytest.raises block -- otherwise the helper raises first and
# the assertion never runs.


def make_course(session, name="Pine Hills", city="Austin", state="TX"):
    course = Course(name=name, city=city, state=state)
    session.add(course)
    session.flush()  # assigns course.id without committing
    return course


def make_tee(session, course, name="Blue", par=72, cr="71.5", slope=130):
    tee = Tee(
        course=course,
        name=name,
        par=par,
        course_rating=Decimal(cr),
        slope_rating=slope,
    )
    session.add(tee)
    session.flush()
    return tee


def make_user(session, email="a@example.com", display_name="Test Golfer"):
    user = User(email=email, display_name=display_name)
    session.add(user)
    session.flush()
    return user


# ---------------------------------------------------------------------------
# Round-tripping
# ---------------------------------------------------------------------------


def test_a_round_survives_a_write_and_a_read(db_session):
    user = make_user(db_session)
    tee = make_tee(db_session, make_course(db_session))
    db_session.add(
        Round(user=user, tee=tee, played_on=date(2025, 6, 14), gross_score=88)
    )
    db_session.flush()
    db_session.expunge_all()  # forces a genuine reload rather than a cache hit

    stored = db_session.scalars(select(Round)).one()

    assert stored.gross_score == 88
    assert stored.played_on == date(2025, 6, 14)
    assert stored.tee.name == "Blue"
    assert stored.tee.course.name == "Pine Hills"


def test_defaults_are_applied(db_session):
    user = make_user(db_session)
    tee = make_tee(db_session, make_course(db_session))
    db_session.add(
        Round(user=user, tee=tee, played_on=date(2025, 6, 14), gross_score=88)
    )
    db_session.flush()
    db_session.expunge_all()

    stored = db_session.scalars(select(Round)).one()

    assert stored.pcc == 0
    assert stored.nine is None  # all eighteen holes
    assert stored.created_at is not None  # the row's birthday, not the round's


def test_a_round_stores_no_handicap_index(db_session):
    """Regression guard on a deliberate removal.

    `rounds` used to carry an `index_at_time` column so that past rounds were
    never regraded against today's number. played_on does that job now -- the
    API grades each round on the rounds played before it -- and the column went
    with the rest of the index machinery. This test fails if it comes back.
    """
    assert "index_at_time" not in Round.__table__.columns


def test_course_rating_keeps_its_exact_decimal(db_session):
    """Numeric, not Float: 71.3 has no exact binary form, and the differential
    formula rounds to one decimal at the end."""
    tee = make_tee(db_session, make_course(db_session), cr="71.3")
    db_session.expunge_all()

    assert db_session.scalars(select(Tee)).one().course_rating == Decimal("71.3")


# ---------------------------------------------------------------------------
# The tees-are-not-courses decision
# ---------------------------------------------------------------------------


def test_one_course_carries_several_tees_with_different_ratings(db_session):
    """The whole reason `tees` is its own table."""
    course = make_course(db_session)
    make_tee(db_session, course, name="Blue", cr="71.5", slope=130)
    make_tee(db_session, course, name="White", cr="69.8", slope=124)
    db_session.expunge_all()

    stored = db_session.scalars(select(Course)).one()
    ratings = {t.name: (float(t.course_rating), t.slope_rating) for t in stored.tees}

    assert ratings == {"Blue": (71.5, 130), "White": (69.8, 124)}


def test_the_same_score_rates_differently_from_different_tees(db_session):
    """Ties the schema to the point of the app: the tee is what makes an 88 mean
    two different things at one golf course."""
    course = make_course(db_session)
    blue = make_tee(db_session, course, name="Blue", cr="71.5", slope=130)
    white = make_tee(db_session, course, name="White", cr="69.8", slope=124)

    from_blue = score_differential(88, float(blue.course_rating), blue.slope_rating)
    from_white = score_differential(88, float(white.course_rating), white.slope_rating)

    assert from_blue < from_white  # the harder tee rates the same score better


def test_stored_values_feed_the_golf_maths(db_session):
    """float() at the boundary is the whole cost of storing ratings as Numeric."""
    tee = make_tee(db_session, make_course(db_session), cr="71.5", slope=130)

    # 14.3 x 130/113 + 71.5 = 87.951 -> 88.0
    assert (
        score_from_differential(14.3, float(tee.course_rating), tee.slope_rating) == 88.0
    )


# ---------------------------------------------------------------------------
# Constraints -- the database as the last line of defence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_slope", [54, 156])
def test_slope_outside_the_whs_range_is_rejected(db_session, bad_slope):
    course = make_course(db_session)
    db_session.add(
        Tee(
            course=course,
            name="Bad",
            par=72,
            course_rating=Decimal("71.5"),
            slope_rating=bad_slope,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_a_non_positive_score_is_rejected(db_session):
    user = make_user(db_session)
    tee = make_tee(db_session, make_course(db_session))
    db_session.add(
        Round(user=user, tee=tee, played_on=date(2025, 1, 1), gross_score=0)
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_pcc_outside_the_whs_range_is_rejected(db_session):
    user = make_user(db_session)
    tee = make_tee(db_session, make_course(db_session))
    db_session.add(
        Round(user=user, tee=tee, played_on=date(2025, 1, 1), gross_score=88, pcc=9)
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_a_course_cannot_have_two_tees_of_the_same_name(db_session):
    course = make_course(db_session)
    make_tee(db_session, course, name="Blue")
    db_session.add(
        Tee(
            course=course,
            name="Blue",
            par=72,
            course_rating=Decimal("71.5"),
            slope_rating=130,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_two_courses_may_share_a_name_in_different_cities(db_session):
    """Course names repeat constantly, so the name alone must not be unique."""
    make_course(db_session, name="Riverside", city="Austin")
    make_course(db_session, name="Riverside", city="Dallas")

    db_session.flush()  # must not raise

    assert len(db_session.scalars(select(Course)).all()) == 2


def test_the_same_email_cannot_register_twice(db_session):
    make_user(db_session, email="dup@example.com")
    db_session.add(User(email="dup@example.com", display_name="Impostor"))

    with pytest.raises(IntegrityError):
        db_session.flush()


# ---------------------------------------------------------------------------
# Cascades
# ---------------------------------------------------------------------------


def test_deleting_a_course_removes_its_tees(db_session):
    course = make_course(db_session)
    make_tee(db_session, course)

    db_session.delete(course)
    db_session.flush()

    assert db_session.scalars(select(Tee)).all() == []


def test_deleting_a_user_removes_their_rounds(db_session):
    user = make_user(db_session)
    tee = make_tee(db_session, make_course(db_session))
    db_session.add(
        Round(user=user, tee=tee, played_on=date(2025, 1, 1), gross_score=88)
    )
    db_session.flush()

    db_session.delete(user)
    db_session.flush()

    assert db_session.scalars(select(Round)).all() == []
    assert db_session.scalars(select(Tee)).all() != []  # the course survives
