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

No handicap index appears anywhere below. The app neither takes one nor
computes one -- see the module docstring in `golf/handicap.py` for why.
"""

from datetime import date

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from golf.handicap import MAX_SLOPE, MIN_SLOPE

# ---------------------------------------------------------------------------
# Shared field definitions
# ---------------------------------------------------------------------------
# These are plain module-level values reused across the models below, so the
# constraints and descriptions are written once. Each model still declares its
# own attributes -- this is deduplication of the *definition*, not inheritance.

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
    """One set of tees, as supplied when adding a course.

    The four nine-hole figures are optional, and they are the ones the USGA
    prints beside the 18-hole numbers as "Front (9)" and "Back (9)". Without
    them a nine played from this tee is logged but left out of the quantiles --
    approximating them costs more than folding nines in gains. See the note in
    `db/models.py`.
    """

    name: str = Field(..., min_length=1, max_length=40, examples=["Blue"])
    par: int = Field(..., gt=0, le=100, examples=[72])
    course_rating: float = _COURSE_RATING
    slope_rating: int = Field(..., ge=MIN_SLOPE, le=MAX_SLOPE, examples=[130])
    yardage: int | None = Field(None, gt=0, examples=[6543])

    front_course_rating: float | None = Field(None, gt=0, le=50, examples=[35.8])
    front_slope_rating: int | None = Field(None, ge=MIN_SLOPE, le=MAX_SLOPE, examples=[130])
    back_course_rating: float | None = Field(None, gt=0, le=50, examples=[36.1])
    back_slope_rating: int | None = Field(None, ge=MIN_SLOPE, le=MAX_SLOPE, examples=[128])

    @model_validator(mode="after")
    def _nine_hole_figures_come_in_pairs(self) -> "TeeCreate":
        """A rating with no slope cannot produce a differential, so reject the
        half-filled state here rather than storing something unusable."""
        for side in ("front", "back"):
            rating = getattr(self, f"{side}_course_rating")
            slope = getattr(self, f"{side}_slope_rating")
            if (rating is None) != (slope is None):
                raise ValueError(
                    f"{side}_course_rating and {side}_slope_rating must be given "
                    "together or not at all."
                )
        return self


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


class TeeUpdate(BaseModel):
    """Corrections to a tee's ratings. Every field optional; omitted means keep.

    This exists because the operation it performs was unreachable. A tee entered
    with only its 18-hole figures could never gain its nine-hole ones, so the
    only way to record a front nine was to invent a second tee -- which is the
    wrong shape, because the front nine is not a different tee, it is the same
    tee played over nine holes. That is how a real backfill ended up with two
    copies of one course.

    Name and par are deliberately absent: they identify the tee. Ratings are
    facts about it that can be typed wrong, and a wrong slope silently shifts
    every round ever played from it — so correcting one has to be possible.
    """

    course_rating: float | None = Field(None, gt=0, le=90)
    slope_rating: int | None = Field(None, ge=MIN_SLOPE, le=MAX_SLOPE)
    front_course_rating: float | None = Field(None, gt=0, le=50)
    front_slope_rating: int | None = Field(None, ge=MIN_SLOPE, le=MAX_SLOPE)
    back_course_rating: float | None = Field(None, gt=0, le=50)
    back_slope_rating: int | None = Field(None, ge=MIN_SLOPE, le=MAX_SLOPE)


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

    # Null when this tee's nines have not been entered. The round-entry screen
    # reads these to decide whether it can offer a nine-hole option at all.
    front_course_rating: float | None
    front_slope_rating: int | None
    back_course_rating: float | None
    back_slope_rating: int | None


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
    pcc: int = Field(0, ge=-1, le=3)
    nine: Literal["front", "back"] | None = Field(
        None,
        description=(
            "Which nine was played, or null for all eighteen. The two nines "
            "carry different Course Ratings and Slopes, so 'a nine' on its own "
            "does not identify what to grade against."
        ),
    )
    notes: str | None = Field(None, max_length=500)


class RoundRead(BaseModel):
    """A stored round, with the derived numbers computed on the way out.

    Nothing derived is stored -- see the convention in CLAUDE.md. The
    differential and both benchmarks are recomputed from the raw rows every time
    they are read, so a formula fix cannot leave the database disagreeing with
    the code.

    Everything below `score_differential` is a quantile of the rounds played
    BEFORE this one, and is null until there are enough of them -- see
    `rounds_until_benchmarks`.

    Scale note: for a nine-hole round every stroke figure here is on the NINE's
    scale. `typical_score` is what this golfer usually shoots over that nine,
    not over eighteen, so `to_typical` compares like with like and the sign
    means the same thing on every row of the list.
    """

    id: int
    played_on: date
    gross_score: int
    course_name: str
    tee_name: str
    nine: Literal["front", "back"] | None
    notes: str | None

    score_differential: float | None = Field(
        None,
        description=(
            "The round on a neutral scale, comparable across courses. Null in "
            "exactly one case: a nine played from a tee whose nine-hole Course "
            "Rating and Slope have not been entered, which cannot be rated at "
            "all. Add them to the tee and this round starts counting."
        ),
    )
    rounds_of_history: int = Field(
        ...,
        description=(
            "How many earlier rounds the two benchmarks were drawn from, capped "
            "at the 20-round window."
        ),
    )
    rounds_until_benchmarks: int = Field(
        ...,
        description=(
            "How many more rounds are needed before this one could have been "
            "graded; 0 once it has been. Nines count the same as eighteens "
            "here. Sent so the screen can show an honest countdown without "
            "hard-coding the minimum, which lives in golf/scoring.py."
        ),
    )

    typical_score: float | None = Field(
        None,
        description=(
            "The median of the earlier differentials, expressed as a score over "
            "the holes THIS round covered. What this golfer usually shoots here."
        ),
    )
    potential_score: float | None = Field(
        None,
        description=(
            "The 20th percentile of the earlier differentials, on the same "
            "scale. What this golfer shoots here when they play well. Not a "
            "handicap and never to be used as one -- see golf/scoring.py."
        ),
    )

    to_typical: float | None = Field(
        None,
        description=(
            "Score minus typical, in golf's to-par orientation: NEGATIVE is "
            "better than usual, POSITIVE is worse. An 88 against a typical of "
            "90.0 is -2.0. A minus sign already means 'under par' to a golfer, "
            "so every stroke-denominated field the app displays runs this way."
        ),
    )
    to_potential: float | None = Field(
        None,
        description=(
            "Score minus potential, same orientation. Negative here means a "
            "round better than this golfer's own best form -- rare by "
            "construction, since potential is a 20th percentile."
        ),
    )
