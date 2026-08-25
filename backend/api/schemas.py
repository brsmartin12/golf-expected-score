"""Request and response shapes for the API, as Pydantic models.

What Pydantic is
----------------
A Pydantic model is a class whose type hints are enforced at runtime. Handing
one to FastAPI buys three things at once:

  1. Parsing and validation. JSON arrives as text; Pydantic turns it into typed
     Python and rejects anything that doesn't fit -- before the route function
     runs. A request with slope_rating "banana" never reaches the math.
  2. A machine-readable schema. FastAPI reads these classes to generate the
     OpenAPI spec that powers the interactive /docs page.
  3. Serialization on the way out. The response model turns the returned object
     back into JSON, and drops anything not declared -- so the shape of a
     response is always exactly what the model says it is.

`Field(...)` attaches constraints and documentation to a single attribute. The
literal `...` (Ellipsis) as the first argument means "required, no default" --
Pydantic idiom that reads oddly the first time you meet it.

Why the bounds are imported, not typed in
-----------------------------------------
MIN_SLOPE / MAX_SLOPE come from `golf.handicap`, which already enforces them.
Retyping 55 and 155 here would create a second source of truth that could drift.
The validation now happens twice on purpose, at two different altitudes:
Pydantic rejects bad input at the HTTP boundary with a helpful 422, and
`handicap.py` still guards itself for any non-HTTP caller.
"""

from pydantic import BaseModel, Field

from golf.handicap import MAX_SLOPE, MIN_SLOPE

# The WHS caps a Handicap Index at 54.0. Better-than-scratch players carry a
# "plus" handicap, which is negative in the arithmetic -- nobody is near -10.
MIN_INDEX = -10.0
MAX_INDEX = 54.0


# ---------------------------------------------------------------------------
# Shared field definitions
# ---------------------------------------------------------------------------
# These are plain module-level values reused across the models below, so the
# constraints and descriptions are written once. Each model still declares its
# own attributes -- this is deduplication of the *definition*, not inheritance.

_HANDICAP_INDEX = Field(
    ...,
    ge=MIN_INDEX,
    le=MAX_INDEX,
    description="Your official WHS Handicap Index. Negative for a plus handicap.",
)
_SLOPE_RATING = Field(
    ...,
    ge=MIN_SLOPE,
    le=MAX_SLOPE,
    description=(
        "Slope Rating of the tee played: how much harder the course gets for a "
        f"bogey golfer than a scratch golfer. {MIN_SLOPE}-{MAX_SLOPE}, 113 is average."
    ),
)
_COURSE_RATING = Field(
    ...,
    gt=0,
    le=90,
    description="Course Rating of the tee played: what a scratch golfer is expected to shoot.",
)
_PAR = Field(
    None,
    gt=0,
    description="Par for the tee played. Optional -- only needed for Course Handicap.",
)


class ExpectedScoreRequest(BaseModel):
    """Inputs for 'what should this handicap shoot on this tee?'"""

    handicap_index: float = _HANDICAP_INDEX
    slope_rating: float = _SLOPE_RATING
    course_rating: float = _COURSE_RATING
    par: int | None = _PAR

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "handicap_index": 10.0,
                    "slope_rating": 130,
                    "course_rating": 71.5,
                    "par": 72,
                }
            ]
        }
    }


class ExpectedScoreResponse(BaseModel):
    """What a given Handicap Index is expected to shoot on a given tee.

    `course_handicap` and `par_plus_course_handicap` are null when the request
    omitted `par`, since both formulas need it.
    """

    expected_score: float = Field(
        ..., description="Handicap Index x (Slope / 113) + Course Rating, to one decimal."
    )
    course_handicap: int | None = Field(
        None, description="Strokes received on this tee, rounded to a whole number."
    )
    par_plus_course_handicap: int | None = Field(
        None,
        description=(
            "The same expectation as a whole number. Identical formula to "
            "expected_score -- the Par term cancels -- so the two can sit up to "
            "half a stroke apart purely from rounding."
        ),
    )


class RoundRequest(BaseModel):
    """Inputs for grading a round that has actually been played."""

    score: float = Field(
        ...,
        gt=0,
        le=200,
        description="Adjusted Gross Score for the round.",
    )
    handicap_index: float = _HANDICAP_INDEX
    slope_rating: float = _SLOPE_RATING
    course_rating: float = _COURSE_RATING
    pcc: float = Field(
        0.0,
        ge=-1,
        le=3,
        description=(
            "Playing Conditions Calculation for the day. Almost always 0; the "
            "WHS allows -1 to +3."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "score": 88,
                    "handicap_index": 10.0,
                    "slope_rating": 130,
                    "course_rating": 71.5,
                    "pcc": 0.0,
                }
            ]
        }
    }


class RoundResponse(BaseModel):
    """How a played round rates -- the whole point of the app, in four numbers."""

    score: float = Field(..., description="The score submitted, echoed back.")
    expected_score: float = Field(
        ..., description="What this Handicap Index was expected to shoot here."
    )
    strokes_vs_expected: float = Field(
        ...,
        description=(
            "Expected minus actual. POSITIVE means you beat your expectation: "
            "a 79 against an expectation of 83.0 is +4.0. This is the ANALYSIS "
            "orientation -- higher is better, so averaging it across a course "
            "or a season reads the natural way. For display, use to_expected."
        ),
    )
    to_expected: float = Field(
        ...,
        description=(
            "The same gap in golf's to-par orientation: POSITIVE is over "
            "(worse), NEGATIVE is under (better). An 88 against an expectation "
            "of 83.0 is +5.0; a 79 is -4.0. Exactly the negative of "
            "strokes_vs_expected, and the one to put in front of a golfer -- a "
            "minus sign already means 'under par', so showing -5.0 for a round "
            "five strokes WORSE than expected inverts the convention every "
            "leaderboard has trained them on."
        ),
    )
    score_differential: float = Field(
        ...,
        description=(
            "The round on a neutral scale, comparable across courses. This is "
            "the number that feeds a Handicap Index."
        ),
    )
    beat_expectation: bool = Field(
        ..., description="Convenience flag: was strokes_vs_expected positive?"
    )
