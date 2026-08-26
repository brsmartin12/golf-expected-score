"""Database connection, sessions, and the ORM models.

Deliberately separate from both `golf` (which must stay framework-free and does
no I/O) and `api` (which should not know how a connection is made):

    api  ->  db  ->  Postgres
    api  ->  golf
    db   ->  golf   (only for the WHS constants the CHECK constraints reuse)

Why the connection objects are exported lazily
----------------------------------------------
`db.session` builds an Engine at import time, reading DATABASE_URL as it stands
*then*. Importing it eagerly here would mean that merely touching anything in
this package -- `db.config`, `db.models`, anything -- pins the connection before
a caller has had the chance to change it.

The test suite does exactly that: it redirects DATABASE_URL at a separate test
database before any engine exists, so a test run cannot touch development data.
The module-level __getattr__ below (PEP 562) defers the import until an
attribute is actually asked for, which keeps `from db import engine` working
while leaving `import db.config` genuinely free of side effects.
"""

from typing import TYPE_CHECKING

from db.models import Base, Course, Round, Tee, User

if TYPE_CHECKING:  # for type checkers and editors only; not executed at runtime
    from db.session import SessionLocal, engine, get_session, session_scope

_LAZY = {"engine", "get_session", "session_scope", "SessionLocal", "DATABASE_URL"}


def __getattr__(name: str):
    """Resolve the connection objects on first use, not at import."""
    if name in _LAZY:
        from db import session as _session

        return getattr(_session, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Base",
    "Course",
    "Round",
    "Tee",
    "User",
    "SessionLocal",
    "engine",
    "get_session",
    "session_scope",
]
