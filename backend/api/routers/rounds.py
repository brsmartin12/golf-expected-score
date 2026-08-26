"""Logging rounds and reading them back.

The after-round moment: a score goes in, and a verdict comes back.

Why a round cannot be read on its own
-------------------------------------
A round's Score Differential is a function of that round alone. Its *verdict*
is not: "was this good?" only means anything against what this golfer usually
shoots, which is a quantile of their other rounds. So the read path here works
on the whole ordered series rather than one row at a time -- `_read_models`
below takes a list and returns a list.

Each round is graded against the rounds played BEFORE it and never against
itself or against later ones. That point-in-time discipline is what keeps the
history stable: grading every past round against today's numbers would rewrite
the whole record every time a new score is logged, and destroy every trend.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user
from api.schemas import RoundCreate, RoundRead
from db import Round, Tee, User, get_session
from golf import (
    MINIMUM_ROUNDS,
    POTENTIAL_QUANTILE,
    TYPICAL_QUANTILE,
    WINDOW,
    score_differential,
    score_from_differential,
    trailing,
)

router = APIRouter(prefix="/rounds", tags=["rounds"])


def _differential(round_: Round) -> float:
    """This round on the neutral scale.

    float() appears because the ratings are Numeric in the database, which reads
    back as Decimal; `golf` works in float. This is the boundary where that
    conversion belongs.
    """
    return score_differential(
        adjusted_gross_score=round_.gross_score,
        course_rating=float(round_.tee.course_rating),
        slope_rating=round_.tee.slope_rating,
        pcc=round_.pcc,
    )


def _read_models(rounds: list[Round]) -> list[RoundRead]:
    """Grade an oldest-first list of rounds, each against the ones before it.

    Nine-hole rounds are carried through with null benchmarks and are left out
    of the population the quantiles are drawn from. The `tees` table stores
    18-hole Course Ratings and Slopes, so running half a round through the
    differential formula produces a number several strokes too low -- one that
    would drag a golfer's typical and potential down for the next twenty rounds.
    """
    differentials = [_differential(r) for r in rounds]

    # Positions in `rounds` that belong in the quantile population, and their
    # differentials in the same order.
    full = [i for i, r in enumerate(rounds) if not r.is_nine_hole]
    full_differentials = [differentials[i] for i in full]

    typical_at = trailing(full_differentials, TYPICAL_QUANTILE)
    potential_at = trailing(full_differentials, POTENTIAL_QUANTILE)

    # Map each full round back to its place in the quantile series, so the
    # per-round lookup below is a dict hit rather than a scan.
    position = {round_index: n for n, round_index in enumerate(full)}

    models = []
    for i, round_ in enumerate(rounds):
        n = position.get(i)

        if n is None:  # a nine-hole round: outside the population entirely
            history = 0
            # Not `MINIMUM_ROUNDS`: no number of further rounds will ever get
            # this one a verdict, so a countdown here would be a promise the app
            # cannot keep. The screen branches on is_nine_hole instead.
            countdown = 0
            typical_differential = potential_differential = None
        else:
            history = min(n, WINDOW)
            countdown = max(0, MINIMUM_ROUNDS - history)
            typical_differential = typical_at[n]
            potential_differential = potential_at[n]

        models.append(
            _one(
                round_,
                differentials[i],
                history,
                countdown,
                typical_differential,
                potential_differential,
            )
        )
    return models


def _one(
    round_: Round,
    differential: float,
    rounds_of_history: int,
    rounds_until_benchmarks: int,
    typical_differential: float | None,
    potential_differential: float | None,
) -> RoundRead:
    """Assemble one round's response, converting differentials back into scores.

    A differential is course-neutral, which is what makes it comparable; a
    golfer is not thinking in differentials. `score_from_differential` puts both
    benchmarks back into strokes on the tee that was actually played, so "you
    usually shoot 90 here" is a sentence about this course.
    """
    tee = round_.tee
    course_rating = float(tee.course_rating)

    def as_score(d: float | None) -> float | None:
        if d is None:
            return None
        return score_from_differential(d, course_rating, tee.slope_rating, round_.pcc)

    typical = as_score(typical_differential)
    potential = as_score(potential_differential)

    # Score minus benchmark: under is negative, and negative is good. See the
    # display convention in ROADMAP.md.
    def gap(benchmark: float | None) -> float | None:
        if benchmark is None:
            return None
        return round(round_.gross_score - benchmark, 1)

    return RoundRead(
        id=round_.id,
        played_on=round_.played_on,
        gross_score=round_.gross_score,
        course_name=tee.course.name,
        tee_name=tee.name,
        is_nine_hole=round_.is_nine_hole,
        notes=round_.notes,
        score_differential=differential,
        rounds_of_history=rounds_of_history,
        rounds_until_benchmarks=rounds_until_benchmarks,
        typical_score=typical,
        potential_score=potential,
        to_typical=gap(typical),
        to_potential=gap(potential),
    )


def _load_rounds(session: Session, user: User) -> list[Round]:
    """This golfer's rounds, oldest played first -- the order the grading needs.

    Ordered by played_on rather than by id, because a backfill enters old rounds
    last, so insertion order and playing order have nothing to do with each
    other. id breaks ties so the order is stable for two rounds on one day.
    """
    return list(
        session.scalars(
            select(Round)
            .where(Round.user_id == user.id)
            .options(selectinload(Round.tee).selectinload(Tee.course))
            .order_by(Round.played_on, Round.id)
        ).all()
    )


@router.get("", response_model=list[RoundRead])
def list_rounds(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[RoundRead]:
    """This golfer's rounds, most recently played first.

    Graded oldest-first, then reversed: the grading needs chronological order,
    the screen wants the newest round at the top.
    """
    return list(reversed(_read_models(_load_rounds(session, user))))


@router.post("", response_model=RoundRead, status_code=status.HTTP_201_CREATED)
def create_round(
    payload: RoundCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> RoundRead:
    """Log a round, and get the verdict back in the same response.

    One request, not two: the post-round moment is "save it and tell me if it
    was any good", and splitting that into a save followed by a fetch would put
    a second network round trip between the golfer and the answer -- on a car
    park connection, which is exactly where that hurts.

    The whole history is reloaded to grade the new round, because a backfilled
    round lands in the middle of it and must be judged on what came before its
    own date, not on the last twenty rounds entered.
    """
    tee = session.get(Tee, payload.tee_id)
    if tee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tee with id {payload.tee_id}.",
        )

    round_ = Round(
        user_id=user.id,
        tee_id=payload.tee_id,
        played_on=payload.played_on,
        gross_score=payload.gross_score,
        pcc=payload.pcc,
        is_nine_hole=payload.is_nine_hole,
        notes=payload.notes,
    )
    session.add(round_)
    session.commit()
    session.refresh(round_)

    graded = {m.id: m for m in _read_models(_load_rounds(session, user))}
    return graded[round_.id]
