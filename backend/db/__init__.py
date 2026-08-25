"""Database connection, sessions, and the ORM models.

Deliberately separate from both `golf` (which must stay framework-free and does
no I/O) and `api` (which should not know how a connection is made). The
dependency arrow grows one more link:

    api  ->  db  ->  Postgres
    api  ->  golf
    db   ->  golf   (only for the WHS constants the CHECK constraints reuse)

`golf` still imports nothing from either, which is what keeps the maths testable
without a database.
"""

from db.models import Base, Course, HandicapSnapshot, Round, Tee, User
from db.session import engine, get_session, session_scope

__all__ = [
    "Base",
    "Course",
    "HandicapSnapshot",
    "Round",
    "Tee",
    "User",
    "engine",
    "get_session",
    "session_scope",
]
