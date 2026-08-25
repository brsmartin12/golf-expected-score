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
