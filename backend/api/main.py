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
These endpoints compute rather than store, so there is no resource to GET.
They are POSTs taking a JSON body: the inputs travel as structured, typed data
instead of being flattened into a query string, and the request models double as
the documented contract for the React app in step 3.

The honest caveat: a pure calculation has no side effects, so GET would be
defensible too and would let responses be cached. POST is the pragmatic choice
here because a JSON body validated by a Pydantic model is a much better fit for
five typed inputs than `?handicap_index=10.0&slope_rating=130&...`.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    ExpectedScoreRequest,
    ExpectedScoreResponse,
    RoundRequest,
    RoundResponse,
)
from golf import (
    course_handicap,
    expected_score,
    score_differential,
    strokes_vs_expected,
)

app = FastAPI(
    title="Golf Expected Score",
    version="0.1.0",
    description=(
        "Turn a raw golf score into a number that means something: what a given "
        "Handicap Index was expected to shoot on a given tee, and how a round "
        "actually played compares to it."
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
    server is actually running and reachable."""
    return {"status": "ok"}


@app.post("/expected-score", response_model=ExpectedScoreResponse, tags=["calculate"])
def calculate_expected_score(payload: ExpectedScoreRequest) -> ExpectedScoreResponse:
    """What a Handicap Index is expected to shoot on this course and tee.

    FastAPI reads the `payload: ExpectedScoreRequest` annotation and infers that
    the JSON body should be parsed into that model. There is no decorator
    argument or manual `request.json()` call -- the type hint *is* the wiring.
    """
    expected = expected_score(
        handicap_index=payload.handicap_index,
        slope_rating=payload.slope_rating,
        course_rating=payload.course_rating,
    )

    # Course Handicap needs par, which is optional on the request. Leave both
    # par-dependent fields null rather than inventing a default of 72 -- a
    # silently wrong par would produce a silently wrong stroke allocation.
    course_hcp = None
    par_plus = None
    if payload.par is not None:
        course_hcp = course_handicap(
            handicap_index=payload.handicap_index,
            slope_rating=payload.slope_rating,
            course_rating=payload.course_rating,
            par=payload.par,
        )
        par_plus = payload.par + course_hcp

    return ExpectedScoreResponse(
        expected_score=expected,
        course_handicap=course_hcp,
        par_plus_course_handicap=par_plus,
    )


@app.post("/round", response_model=RoundResponse, tags=["calculate"])
def evaluate_round(payload: RoundRequest) -> RoundResponse:
    """Grade a round that was actually played.

    Returns the score alongside what was expected, the gap between them in both
    orientations (see the schema), and the Score Differential -- the
    neutral-scale version that makes an 88 on a brutal course comparable to an
    88 on an easy one.
    """
    expected = expected_score(
        handicap_index=payload.handicap_index,
        slope_rating=payload.slope_rating,
        course_rating=payload.course_rating,
    )
    versus = strokes_vs_expected(
        score=payload.score,
        handicap_index=payload.handicap_index,
        slope_rating=payload.slope_rating,
        course_rating=payload.course_rating,
    )
    differential = score_differential(
        adjusted_gross_score=payload.score,
        course_rating=payload.course_rating,
        slope_rating=payload.slope_rating,
        pcc=payload.pcc,
    )

    return RoundResponse(
        score=payload.score,
        expected_score=expected,
        strokes_vs_expected=versus,
        # Negated rather than recomputed from score - expected, so the two can
        # never disagree by a rounding step.
        to_expected=-versus,
        score_differential=differential,
        beat_expectation=versus > 0,
    )
