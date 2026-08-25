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

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from db.config import database_url


def _point_at_a_separate_test_database() -> None:
    """Redirect DATABASE_URL at `<name>_test` for the whole test session.

    Tests write real rows and assert on what comes back, so they need a database
    that is theirs alone. Sharing the development one breaks both ways: rows
    left over from clicking around the app make tests fail for no reason, and a
    fixture that wiped the database clean would destroy work in progress.

    This must run before anything imports db.session, because that module builds
    its Engine at import time from whatever DATABASE_URL says then -- which is
    exactly why db/config.py exists separately and has no side effects.

    Set TEST_DATABASE_URL to override, or to point tests at an entirely
    different server.
    """
    if os.getenv("TEST_DATABASE_URL"):
        os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
        return

    url = make_url(database_url())
    if url.database is None or url.database.endswith("_test"):
        return  # already a test database, or nothing to derive a name from

    test_url = url.set(database=f"{url.database}_test")

    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT, and it
    # has to be issued from a connection to some *other* database.
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_url.database},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    except Exception:  # noqa: BLE001 - no server, or no permission to create
        return  # leave DATABASE_URL alone; the skip marker below handles it
    finally:
        admin.dispose()

    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)


_point_at_a_separate_test_database()

from db import engine  # noqa: E402 - must follow the redirect above


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
    # join_transaction_mode="create_savepoint" is what makes this work for code
    # that commits -- and the routes do commit, since a real request has to.
    #
    # Without it, a session bound to a connection that already has a transaction
    # commits THAT transaction, so the rollback below has nothing left to undo
    # and rows leak into every later test. With it, the session works inside a
    # SAVEPOINT: its commits release the savepoint, the outer transaction stays
    # open, and the rollback still wipes everything.
    session = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")
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
