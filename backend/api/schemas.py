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

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

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


class PotentialScoreRequest(BaseModel):
    """Inputs for 'what does this handicap shoot here when it plays well?'"""

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


class PotentialScoreResponse(BaseModel):
    """What a given Handicap Index posts on a given tee when it plays well.

    NOT its typical score: an index averages the best 8 of the last 20
    differentials, so this is roughly a top-quartile round. The typical figure
    needs a scoring record and arrives with the analytics layer.

    `course_handicap` and `par_plus_course_handicap` are null when the request
    omitted `par`, since both formulas need it.
    """

    potential_score: float = Field(
        ...,
        description=(
            "Handicap Index x (Slope / 113) + Course Rating, to one decimal. The "
            "score this index posts when it plays WELL -- not its typical score."
        ),
    )
    course_handicap: int | None = Field(
        None, description="Strokes received on this tee, rounded to a whole number."
    )
    par_plus_course_handicap: int | None = Field(
        None,
        description=(
            "The same potential as a whole number. Identical formula to "
            "potential_score -- the Par term cancels -- so the two can sit up to "
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
    """How a played round rates -- the whole point of the app, in a few numbers."""

    score: float = Field(..., description="The score submitted, echoed back.")
    potential_score: float = Field(
        ..., description="What this Handicap Index posts here when it plays well."
    )
    strokes_vs_potential: float = Field(
        ...,
        description=(
            "Potential minus actual. POSITIVE means you beat your potential: "
            "a 79 against a potential of 83.0 is +4.0. This is the ANALYSIS "
            "orientation -- higher is better, so averaging it across a course "
            "or a season reads the natural way. For display, use to_potential."
        ),
    )
    to_potential: float = Field(
        ...,
        description=(
            "The same gap in golf's to-par orientation: POSITIVE is over "
            "(worse), NEGATIVE is under (better). An 88 against a potential "
            "of 83.0 is +5.0; a 79 is -4.0. Exactly the negative of "
            "strokes_vs_potential, and the one to put in front of a golfer -- a "
            "minus sign already means 'under par', so showing -5.0 for a round "
            "five strokes WORSE than their potential inverts the convention every "
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
    beat_potential: bool = Field(
        ..., description="Convenience flag: was strokes_vs_potential positive?"
    )


# ---------------------------------------------------------------------------
# Stored data: courses, tees and rounds
# ---------------------------------------------------------------------------
# The models above describe calculations, which take inputs and return numbers.
# These describe *rows*, which is a different job, and it brings one new tool:
#
#   model_config = ConfigDict(from_attributes=True)
#
# By default Pydantic builds a model from a dict. from_attributes lets it build
# one from any object with matching attributes -- a SQLAlchemy row, in other
# words. That is what lets a route return a `Round` and have FastAPI serialise
# it through `RoundRead` without any manual field copying.
#
# Two layers of models rather than one, on purpose. The ORM model is the shape
# of the table; the schema is the shape of the JSON. Returning ORM objects
# directly would mean any column added later is published to the API by
# accident -- including ones that should not be, like another user's id.


class TeeCreate(BaseModel):
    """One set of tees, as supplied when adding a course."""

    name: str = Field(..., min_length=1, max_length=40, examples=["Blue"])
    par: int = Field(..., gt=0, le=100, examples=[72])
    course_rating: float = _COURSE_RATING
    slope_rating: int = Field(..., ge=MIN_SLOPE, le=MAX_SLOPE, examples=[130])
    yardage: int | None = Field(None, gt=0, examples=[6543])


class CourseCreate(BaseModel):
    """A course and its tees, added together.

    Nested on purpose: a course with no tees is useless, since every number this
    app computes needs a Slope and a Course Rating. Requiring at least one tee
    up front makes the useless state unrepresentable rather than merely
    discouraged.
    """

    name: str = Field(..., min_length=1, max_length=120, examples=["Pine Hills"])
    city: str | None = Field(None, max_length=80, examples=["Austin"])
    state: str | None = Field(None, max_length=40, examples=["TX"])
    tees: list[TeeCreate] = Field(..., min_length=1)


class TeeRead(BaseModel):
    """A tee as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    par: int
    # Declared float although the column is Numeric: Pydantic coerces the
    # Decimal on the way out, so JSON carries a number rather than a string.
    course_rating: float
    slope_rating: int
    yardage: int | None


class CourseRead(BaseModel):
    """A course with its tees -- what the course picker renders."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str | None
    state: str | None
    tees: list[TeeRead]


class RoundCreate(BaseModel):
    """A round being logged. The post-round moment, in one request."""

    tee_id: int
    played_on: date = Field(
        ...,
        description=(
            "The date the round was PLAYED, which is not necessarily today -- "
            "backfilled history is entered with its original date."
        ),
    )
    gross_score: int = Field(..., gt=0, le=200, examples=[88])
    index_at_time: float | None = Field(
        None,
        ge=MIN_INDEX,
        le=MAX_INDEX,
        description=(
            "Handicap Index in effect on the day. Optional: leave it out for "
            "backfilled rounds, where it is derivable from the surrounding "
            "rounds rather than remembered."
        ),
    )
    pcc: int = Field(0, ge=-1, le=3)
    is_nine_hole: bool = False
    notes: str | None = Field(None, max_length=500)


class RoundRead(BaseModel):
    """A stored round, with the derived numbers computed on the way out.

    Nothing derived is stored -- see the convention in CLAUDE.md. The
    differential, the potential and the gap are all recomputed from the raw row
    every time it is read, so a formula fix cannot leave the database
    disagreeing with the code.

    `score_differential` is always present: it needs only the score, the rating,
    the slope and the PCC. The three index-dependent fields are null when
    `index_at_time` is unknown, which is the normal case for backfilled rounds
    until the Tier 2 analytics can derive it.
    """

    id: int
    played_on: date
    gross_score: int
    course_name: str
    tee_name: str
    is_nine_hole: bool
    notes: str | None

    score_differential: float
    index_at_time: float | None
    potential_score: float | None
    strokes_vs_potential: float | None
    to_potential: float | None
