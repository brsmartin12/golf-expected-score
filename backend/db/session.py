"""The engine and the session factory -- the two objects everything else needs.

What an ORM is, and why bother
------------------------------
Without one, talking to Postgres means writing SQL strings, sending them over a
connection, and turning the returned tuples back into something Python-shaped by
hand. That works, but every query becomes string assembly, and the shape of a
row lives in your head rather than anywhere the interpreter can check.

SQLAlchemy is an ORM: an Object-Relational Mapper. It maps rows to Python
objects and back. You declare `Round` as a class once, and reading gives you
`Round` instances with real attributes, while writing takes those instances and
generates the INSERT. Two things it buys that matter here:

  - The schema is written down in Python, in one place, so a column rename is a
    change the tooling can find rather than a grep.
  - It generates parameterised SQL, so a course named "O'Malley's" cannot break
    a query or become an injection bug.

Two objects, and the difference between them
--------------------------------------------
An **Engine** is the connection pool, created once when the process starts. It
is not itself a connection -- it knows how to hand them out and take them back.
Creating one per request would be a serious performance bug.

A **Session** is a unit of work, created per request and thrown away after. It
holds the objects you have loaded or created, tracks what changed, and flushes
those changes as SQL when you commit. Roughly: the engine is the pipe, the
session is one conversation through it.

Why the URL comes from the environment
--------------------------------------
The connection string carries a password and differs per environment, so it
cannot be committed. `DATABASE_URL` is read from the environment, with a local
default so nothing has to be configured to get started. Same idea as
VITE_API_URL on the frontend.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Loads backend/.env into the environment if it exists. Real environment
# variables always win, so a deployed setting is never overridden by a stray
# local file.
load_dotenv()

# "postgresql+psycopg://" picks the psycopg 3 driver explicitly. Without the
# +psycopg suffix SQLAlchemy reaches for psycopg2, which is not installed here.
DEFAULT_DATABASE_URL = "postgresql+psycopg://golf@127.0.0.1:5432/golf"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    # Checks a pooled connection is still alive before handing it over. Hosted
    # Postgres providers drop idle connections, and without this the first
    # request after a quiet spell fails with a stale-connection error.
    pool_pre_ping=True,
    # Set SQL_ECHO=1 to print every statement SQLAlchemy runs. Genuinely the
    # fastest way to learn what an ORM is actually doing on your behalf.
    echo=os.getenv("SQL_ECHO") == "1",
)

# A factory, not a session: calling SessionLocal() makes a new one.
#
# expire_on_commit=False means objects stay readable after commit. The default
# marks every attribute stale so the next access silently re-queries -- which
# raises errors when the session has already closed, a confusing first bug.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session():
    """FastAPI dependency: one session per request, always closed.

    Declaring `session: Session = Depends(get_session)` on a route makes FastAPI
    run this, hand the yielded session to the route, and then resume it after
    the response is sent -- so the `with` block closes the session and returns
    its connection to the pool even if the route raised.
    """
    with SessionLocal() as session:
        yield session


def session_scope() -> Session:
    """A session for code that is not a web request -- scripts, imports, the REPL.

    Use as a context manager: `with session_scope() as session:`. Same object a
    route gets, without FastAPI's dependency machinery in the way.
    """
    return SessionLocal()
