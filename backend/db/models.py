"""The tables, as Python classes.

How this works
--------------
Every model below subclasses `Base`. SQLAlchemy collects those subclasses into
`Base.metadata`, which is a full description of the schema -- enough to create
the tables, and later enough for Alembic to diff against a live database and
write a migration.

`Mapped[int]` and `mapped_column(...)` are the SQLAlchemy 2.0 style. The type
annotation carries real information: `Mapped[int]` becomes a NOT NULL integer
column, `Mapped[int | None]` a nullable one. So nullability is stated once, in
the annotation, rather than in a separate keyword that can disagree with it.

Two conventions worth stating once
----------------------------------
- **Slope Rating is an Integer.** WHS slope ratings are whole numbers, always.
- **Course Rating is Numeric(4, 1), not Float.** A rating like 71.3 has no exact
  binary representation, and the differential formula rounds to one decimal at
  the end -- so a float error could, at an exact .05 boundary, flip the last
  digit. Numeric stores it exactly. The cost is that reads give `Decimal`, so
  values are cast with float() at the boundary where they enter `golf`.

What is deliberately NOT here
-----------------------------
No differentials, no course handicaps, no potential scores. Those are derived on
read by `golf/handicap.py`. Persisting them would mean a formula fix leaves the
database quietly disagreeing with the code -- see the convention in CLAUDE.md.
"""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from golf.handicap import MAX_SLOPE, MIN_SLOPE


class Base(DeclarativeBase):
    """The registry every model attaches itself to."""


class User(Base):
    """A golfer.

    Present from the first migration even though authentication is not until
    step 10, because adding a column later is easy and adding a tenancy boundary
    to tables already full of data is not. Until auth ships there is one row.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rounds: Mapped[list["Round"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    handicap_snapshots: Mapped[list["HandicapSnapshot"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience
        return f"<User {self.display_name!r}>"


class Course(Base):
    """A golf course. Holds no slope or rating -- those live on `Tee`."""

    __tablename__ = "courses"
    __table_args__ = (
        # Course names repeat across the country, so the name alone is not
        # unique. Name plus location is close enough to catch a double entry.
        UniqueConstraint("name", "city", "state", name="uq_course_name_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    city: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(40))

    tees: Mapped[list["Tee"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Course {self.name!r}>"


class Tee(Base):
    """One set of tees at a course -- the blues, the whites, the reds.

    This is its own table rather than columns on `Course` because Slope and
    Course Rating are properties of the *tee*, not the course: the blues and the
    whites at the same club rate differently, which is the entire reason a
    Course Handicap depends on which tees you played. Collapsing the two is the
    classic mistake here, and it is expensive to undo once rounds point at it.
    """

    __tablename__ = "tees"
    __table_args__ = (
        UniqueConstraint("course_id", "name", name="uq_tee_course_name"),
        # The database is the last line of defence, after the Pydantic models
        # and golf/handicap.py's own guards. It is the one that also catches a
        # bad seed script or a hand-written INSERT.
        CheckConstraint(
            f"slope_rating BETWEEN {MIN_SLOPE} AND {MAX_SLOPE}",
            name="ck_tee_slope_in_whs_range",
        ),
        CheckConstraint("course_rating > 0", name="ck_tee_course_rating_positive"),
        CheckConstraint("par > 0", name="ck_tee_par_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(40))
    par: Mapped[int] = mapped_column(Integer)
    course_rating: Mapped[Numeric] = mapped_column(Numeric(4, 1))
    slope_rating: Mapped[int] = mapped_column(Integer)
    yardage: Mapped[int | None] = mapped_column(Integer)

    course: Mapped["Course"] = relationship(back_populates="tees")
    rounds: Mapped[list["Round"]] = relationship(back_populates="tee")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tee {self.name!r} CR {self.course_rating}/{self.slope_rating}>"


class Round(Base):
    """One round played: who, where, when, and what they shot.

    Score-only by design -- no hole-by-hole, no fairways or putts. See the scope
    decision in CLAUDE.md: a round has to stay a fifteen-second entry.
    """

    __tablename__ = "rounds"
    __table_args__ = (
        CheckConstraint("gross_score > 0", name="ck_round_score_positive"),
        CheckConstraint("pcc BETWEEN -1 AND 3", name="ck_round_pcc_in_whs_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tee_id: Mapped[int] = mapped_column(ForeignKey("tees.id"))

    # When it was PLAYED. Distinct from created_at below, and the distinction
    # matters immediately: a backfilled round is played_on 2024 but created now.
    played_on: Mapped[date] = mapped_column(Date)
    gross_score: Mapped[int] = mapped_column(Integer)

    # The Handicap Index in effect on the day, and nullable on purpose.
    #
    # Historical strokes-vs-potential must never be recomputed against *today's*
    # index -- that silently rewrites every past round and destroys every trend.
    # But nobody remembers their index from a Saturday two years ago, which would
    # make hand-backfilling impossible if this were required. It does not have to
    # be remembered: once rounds are stored with dates, the index at any date is
    # derivable as the best 8 of the trailing 20 differentials. So: recorded when
    # genuinely known, derived when not.
    index_at_time: Mapped[Numeric | None] = mapped_column(Numeric(3, 1))

    # Playing Conditions Calculation for the day. Almost always 0.
    pcc: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # Nine-hole rounds are stored but not yet handled by the maths -- the WHS
    # combines two nines into an 18-hole differential, which is not implemented.
    is_nine_hole: Mapped[bool] = mapped_column(default=False, server_default="false")

    notes: Mapped[str | None] = mapped_column(String(500))

    # When the ROW was created, as opposed to when the round was played. Cheap
    # now, and the only way to tell a backfilled round from a fresh one later.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="rounds")
    tee: Mapped["Tee"] = relationship(back_populates="rounds")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Round {self.gross_score} on {self.played_on}>"


class HandicapSnapshot(Base):
    """A Handicap Index as it stood on a given date.

    Separate from `rounds.index_at_time` and serving a different purpose: this
    records the *official* index published by a handicap service, which can
    legitimately differ from what this app computes -- different rounds posted,
    a real PCC, the WHS safeguards. Keeping both means the app can show its own
    figure against the official one without either overwriting the other.
    """

    __tablename__ = "handicap_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "effective_on", name="uq_snapshot_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    effective_on: Mapped[date] = mapped_column(Date)
    index_value: Mapped[Numeric] = mapped_column(Numeric(3, 1))

    user: Mapped["User"] = relationship(back_populates="handicap_snapshots")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<HandicapSnapshot {self.index_value} on {self.effective_on}>"
