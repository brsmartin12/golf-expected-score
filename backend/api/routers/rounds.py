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

Two scales in one list
----------------------
A nine-hole round is rated against that nine's own Course Rating and Slope, so
its differential is on a half scale. `golf.scoring` folds it onto the 18-hole
scale for the quantiles; this module does the reverse on the way out, turning
the 18-hole benchmarks back into a score over the holes that were actually
played. A nine is therefore compared against a typical NINE, and the numbers on
every row of the list mean the same thing.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user
from api.schemas import RoundCreate, RoundRead
from db import Round, Tee, User, get_session
from golf import Played, benchmarks, score_differential, score_from_differential

router = APIRouter(prefix="/rounds", tags=["rounds"])


def _holes_played(round_: Round) -> tuple[float, int] | None:
    """The Course Rating and Slope for the holes this round actually covered.

    None when a nine was played from a tee whose nine-hole figures are missing.
    That round cannot be rated at all -- the 18-hole numbers would call half a
    round several strokes better than it was -- so it is carried through
    ungraded rather than approximated.

    float() appears because the ratings are Numeric in the database, which reads
    back as Decimal; `golf` works in float. This is the boundary where that
    conversion belongs.
    """
    tee = round_.tee

    if round_.nine is None:
        return float(tee.course_rating), tee.slope_rating

    if round_.nine == "front":
        rating, slope = tee.front_course_rating, tee.front_slope_rating
    else:
        rating, slope = tee.back_course_rating, tee.back_slope_rating

    if rating is None or slope is None:
        return None
    return float(rating), slope


def _pcc(round_: Round) -> float:
    """Half a day's Playing Conditions adjustment applies to half a round."""
    return round_.pcc / 2 if round_.nine else float(round_.pcc)


def _read_models(rounds: list[Round]) -> list[RoundRead]:
    """Grade an oldest-first list of rounds, each against the ones before it."""
    ratings = [_holes_played(r) for r in rounds]

    differentials: list[float | None] = []
    for round_, rating in zip(rounds, ratings):
        if rating is None:
            differentials.append(None)
            continue
        course_rating, slope = rating
        differentials.append(
            score_differential(round_.gross_score, course_rating, slope, _pcc(round_))
        )

    # Rounds that can be rated, in order, and where each sits in `rounds`.
    usable = [i for i, d in enumerate(differentials) if d is not None]
    series = [
        Played(differentials[i], is_nine=rounds[i].nine is not None) for i in usable
    ]
    marks = benchmarks(series)
    position = {round_index: n for n, round_index in enumerate(usable)}

    models = []
    for i, round_ in enumerate(rounds):
        n = position.get(i)
        models.append(
            _one(
                round_,
                differentials[i],
                ratings[i],
                marks[n] if n is not None else None,
            )
        )
    return models


def _one(
    round_: Round,
    differential: float | None,
    ratings: tuple[float, int] | None,
    mark,
) -> RoundRead:
    """Assemble one round's response, converting benchmarks back into scores.

    A differential is course-neutral, which is what makes it comparable; a
    golfer is not thinking in differentials. `score_from_differential` puts both
    benchmarks back into strokes on the holes that were played, so "you usually
    shoot 90 here" is a sentence about this course.

    For a nine, the 18-hole benchmark is halved before conversion -- half a
    golfer's typical differential IS their typical nine -- and then run through
    the nine's own rating and slope. No approximation enters: those are the
    published figures for that side.
    """
    tee = round_.tee
    share = 0.5 if round_.nine else 1.0

    def as_score(differential_18: float | None) -> float | None:
        if differential_18 is None or ratings is None:
            return None
        course_rating, slope = ratings
        return score_from_differential(
            differential_18 * share, course_rating, slope, _pcc(round_)
        )

    typical = as_score(mark.typical if mark else None)
    potential = as_score(mark.potential if mark else None)

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
        nine=round_.nine,
        notes=round_.notes,
        score_differential=differential,
        rounds_of_history=mark.rounds_of_history if mark else 0,
        rounds_until_benchmarks=mark.rounds_until_benchmarks if mark else 0,
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
        nine=payload.nine,
        notes=payload.notes,
    )
    session.add(round_)
    session.commit()
    session.refresh(round_)

    graded = {m.id: m for m in _read_models(_load_rounds(session, user))}
    return graded[round_.id]


@router.delete("/{round_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_round(
    round_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> None:
    """Remove a round. The escape hatch for a mistyped score.

    Rounds were append-only, which is fine until a backfill of thirty hand-typed
    entries -- one wrong score then sits in the history dragging typical, with
    no way out but hand-written SQL. Delete and retype is enough for that; a
    full edit form is a bigger thing that can wait for a reason.

    A round belonging to someone else is a 404, not a 403. 403 would confirm the
    id exists, which is a small leak but a free one to avoid.

    Deleting changes the verdict on every LATER round, because each one is
    graded against the rounds before it and the population just changed. That
    happens on its own: nothing derived is stored, so the next read recomputes
    it. Callers holding a list should refetch rather than splice.
    """
    round_ = session.get(Round, round_id)
    if round_ is None or round_.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No round with id {round_id}.",
        )

    session.delete(round_)
    session.commit()
