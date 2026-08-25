"""Tests for the database connection itself.

Nothing here tests golf. It tests that the plumbing added in build-order step 4
works: that the URL resolves, the driver loads, a session opens and closes, and
the route wired to it answers.
"""

from sqlalchemy import text

from db import engine, session_scope
from tests.conftest import requires_database


@requires_database
def test_the_engine_can_connect():
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar() == 1


@requires_database
def test_it_is_actually_postgres():
    """Guards against a well-meaning switch to SQLite: the analytics tiers lean
    on Postgres, and the two disagree about dates, types and ordering in ways
    that surface late."""
    assert engine.dialect.name == "postgresql"


@requires_database
def test_session_scope_yields_a_usable_session():
    with session_scope() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1


@requires_database
def test_a_session_returns_its_connection_to_the_pool():
    """The pool only works if connections come back. A session left open per
    request exhausts the pool, and the app then hangs waiting for one rather
    than erroring -- a miserable thing to diagnose from the outside.

    checkedout() is the number of connections currently lent out, so this
    asserts the borrow and the return, not just that the code ran.
    """
    before = engine.pool.checkedout()

    with session_scope() as session:
        session.execute(text("SELECT 1"))
        assert engine.pool.checkedout() == before + 1

    assert engine.pool.checkedout() == before


@requires_database
def test_the_readiness_route_reports_the_database_up():
    """The same session machinery, reached through FastAPI's Depends()."""
    from fastapi.testclient import TestClient

    from api.main import app

    response = TestClient(app).get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"database": "ok"}


def test_liveness_does_not_touch_the_database():
    """Deliberately NOT marked requires_database: /health must answer even when
    Postgres is unreachable, or a database blip gets a healthy container
    restarted by the platform."""
    from fastapi.testclient import TestClient

    from api.main import app

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
