"""Logging rounds and reading them back.

The after-round moment: a score goes in, and a verdict comes back.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user
from api.schemas import RoundCreate, RoundRead
from db import Round, Tee, User, get_session
from golf import potential_score, score_differential, strokes_vs_potential

router = APIRouter(prefix="/rounds", tags=["rounds"])


def _to_read_model(round_: Round) -> RoundRead:
    """Recompute every derived number from the raw row.

    Nothing derived is stored -- see the convention in CLAUDE.md. Differentials,
    potentials and the gap are all computed here on the way out, so a formula
    fix takes effect everywhere at once instead of leaving old rows disagreeing
    with the code.

    float() appears because the ratings are Numeric in the database, which reads
    back as Decimal; `golf` works in float. This is the boundary where that
    conversion belongs.

    The differential needs no index, so it is always present. The three
    index-dependent numbers are null when index_at_time is unknown -- the normal
    case for a backfilled round, until the Tier 2 analytics can derive it from
    the surrounding rounds.
    """
    tee = round_.tee
    course_rating = float(tee.course_rating)

    differential = score_differential(
        adjusted_gross_score=round_.gross_score,
        course_rating=course_rating,
        slope_rating=tee.slope_rating,
        pcc=round_.pcc,
    )

    index = float(round_.index_at_time) if round_.index_at_time is not None else None
    potential = versus = to_potential = None

    if index is not None:
        potential = potential_score(index, tee.slope_rating, course_rating)
        versus = strokes_vs_potential(
            score=round_.gross_score,
            handicap_index=index,
            slope_rating=tee.slope_rating,
            course_rating=course_rating,
        )
        # Negated for display: over is positive, and positive is worse. See the
        # to-par convention in ROADMAP.md.
        to_potential = -versus

    return RoundRead(
        id=round_.id,
        played_on=round_.played_on,
        gross_score=round_.gross_score,
        course_name=tee.course.name,
        tee_name=tee.name,
        is_nine_hole=round_.is_nine_hole,
        notes=round_.notes,
        score_differential=differential,
        index_at_time=index,
        potential_score=potential,
        strokes_vs_potential=versus,
        to_potential=to_potential,
    )


@router.get("", response_model=list[RoundRead])
def list_rounds(
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[RoundRead]:
    """This golfer's rounds, most recently played first.

    Ordered by played_on rather than by id, because a backfill enters old rounds
    last -- so insertion order and playing order have nothing to do with each
    other. id breaks ties so the order is stable for two rounds on one day.
    """
    rounds = session.scalars(
        select(Round)
        .where(Round.user_id == user.id)
        .options(selectinload(Round.tee).selectinload(Tee.course))
        .order_by(Round.played_on.desc(), Round.id.desc())
    ).all()

    return [_to_read_model(r) for r in rounds]


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
        index_at_time=payload.index_at_time,
        pcc=payload.pcc,
        is_nine_hole=payload.is_nine_hole,
        notes=payload.notes,
    )
    session.add(round_)
    session.commit()
    session.refresh(round_)

    return _to_read_model(round_)
