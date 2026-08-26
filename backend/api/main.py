"""The FastAPI application: HTTP routes over the calculations in `golf`.

Running it locally
------------------
    cd backend
    uvicorn api.main:app --reload

`api.main:app` is "import the module api.main, use the object named app".
Uvicorn is an ASGI server -- it owns the socket, accepts connections, and calls
into the app. FastAPI itself never listens on a port; it only knows how to turn
a request into a response. `--reload` restarts on file changes.

Then open http://127.0.0.1:8000/docs to poke at the endpoints in a browser.

Route design
------------
This file holds only the app object, the middleware, the error handling and the
health checks. Every route that does real work lives in a router under
api/routers/ and is mounted below.

There is deliberately no calculator endpoint. There was one -- POST
/potential-score, taking a Handicap Index and returning a score -- and it went
when the app stopped computing an index at all (see the module docstring in
golf/handicap.py). Nothing is lost: the USGA already ships that calculator, and
the numbers this app puts on screen come from a golfer's own rounds, which
means they hang off /rounds rather than off a form.
"""

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

from api.routers import courses, rounds

app = FastAPI(
    title="Golf Expected Score",
    version="0.1.0",
    description=(
        "Turn a raw golf score into a number that means something. Log a round "
        "and it comes back graded against what you typically shoot and what you "
        "shoot when you play well -- both drawn from your own scoring record."
    ),
)

# CORS: browsers refuse cross-origin requests unless the server opts in.
#
# The React dev server (step 3) will run on a different port than this API, and
# a *different port is a different origin*. Without this middleware the browser
# blocks the response and the frontend sees an opaque network error -- with the
# request having succeeded server-side, which makes it a confusing first bug.
# Note that this is a browser rule: curl and the tests are unaffected.
#
# Vite serves on 5173, Create React App on 3000. Both spellings of localhost are
# listed because they are, to the browser, distinct origins.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# Mounting the routers. Each one carries its own prefix and tags, so this is the
# whole of the wiring -- the routes themselves live in api/routers/.
app.include_router(courses.router)
app.include_router(rounds.router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Turn a ValueError from the math layer into a 422 instead of a 500.

    The Pydantic models should catch every bad input before it gets this far, so
    reaching this handler means the two validation layers have drifted apart.
    It exists so that when they do, the client gets a readable message and a
    status code that correctly blames the request -- rather than a bare 500,
    which claims the server is broken when the input was simply wrong.
    """
    # Spelled as a literal rather than status.HTTP_422_*: Starlette renamed
    # the constant (ENTITY -> CONTENT) and the number is the stable spelling.
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness check. Deployment platforms poll something like this to decide
    whether a container came up; it is also the quickest way to confirm the
    server is actually running and reachable.

    Deliberately does NOT touch the database: a liveness check that depends on
    Postgres will report the app as dead during a database blip, and some
    platforms respond by restarting a perfectly healthy container. See
    /health/db for the readiness version."""
    return {"status": "ok"}


@app.get("/health/db", tags=["meta"])
def health_db(session: Session = Depends(get_session)) -> dict[str, str]:
    """Readiness check: can the app actually reach Postgres?

    `Depends(get_session)` is FastAPI's dependency injection. The annotation
    tells FastAPI to call get_session, pass the session it yields in as this
    argument, and close it afterwards -- the route never opens or closes a
    connection itself.

    SELECT 1 is the cheapest possible round trip: it proves the URL, the
    credentials, the network path and the pool all work, without depending on
    any table existing.

    text() is required because SQLAlchemy 2.0 will not accept a bare string as
    a query -- a small guard rail against accidentally interpolating user input
    into SQL.
    """
    session.execute(text("SELECT 1"))
    return {"database": "ok"}
