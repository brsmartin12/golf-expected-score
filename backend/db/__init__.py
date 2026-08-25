"""Database connection and session handling.

Deliberately separate from both `golf` (which must stay framework-free and does
no I/O) and `api` (which should not know how a connection is made). The
dependency arrow grows one more link:

    api  ->  db  ->  Postgres
    api  ->  golf

`golf` still imports nothing from either, which is what keeps the maths
testable without a database.
"""

from db.session import engine, get_session, session_scope

__all__ = ["engine", "get_session", "session_scope"]
