"""Shared pytest fixtures and markers.

conftest.py is a file pytest imports automatically before collecting tests;
anything defined here is available to every test file in this directory tree
without being imported.

Why the skip marker exists
--------------------------
Most of this suite is pure functions and needs nothing running. The database
tests obviously do. Rather than have `pytest` fail for anyone who has not
started Postgres yet, those tests skip with a message saying why -- so a fresh
clone can still run the suite and see the maths pass.
"""

import pytest
from sqlalchemy import text

from db import engine


def _database_is_reachable() -> bool:
    """One connection attempt at import time, so the check runs once, not per test."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any failure means "no database", the reason is in the skip
        return False


DATABASE_IS_REACHABLE = _database_is_reachable()

requires_database = pytest.mark.skipif(
    not DATABASE_IS_REACHABLE,
    reason=(
        "no database reachable at DATABASE_URL -- "
        "run `docker compose up -d` from the repo root, or point DATABASE_URL elsewhere"
    ),
)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _tables():
    """Create the schema once for the whole test session, then drop it.

    Runs against the real database rather than an in-memory stand-in, because
    the things worth testing here -- CHECK constraints, foreign keys, cascade
    deletes -- are enforced by Postgres, not by SQLAlchemy.
    """
    from db.models import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(_tables):
    """A session whose writes are always rolled back.

    Each test gets a connection with an open transaction, and the session is
    bound to that connection. Whatever the test writes is visible to it -- real
    SQL, really executed, constraints really enforced -- and then the outer
    transaction is rolled back, so the next test starts from an empty database.

    Faster than recreating tables per test, and it means tests cannot leak rows
    into each other and pass or fail depending on the order they ran in.
    """
    from db.session import SessionLocal

    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        # A test that provokes an IntegrityError leaves Postgres to abort the
        # transaction itself, which deassociates it from the connection. Rolling
        # back unconditionally then warns about undoing something already undone.
        if transaction.is_active:
            transaction.rollback()
        connection.close()
