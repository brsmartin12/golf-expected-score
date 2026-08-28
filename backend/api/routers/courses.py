"""Courses and their tees.

Read-heavy: this is what the course picker renders, and what both the
before-round and after-round screens need before they can say anything.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from api.schemas import CourseCreate, CourseRead, TeeCreate, TeeUpdate
from db import Course, Tee, get_session

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseRead])
def list_courses(session: Session = Depends(get_session)) -> list[Course]:
    """Every course, with its tees.

    `selectinload(Course.tees)` matters more than it looks. Without it,
    serialising N courses triggers one query for the courses and then one more
    per course to fetch its tees -- the N+1 problem, which is invisible with
    three rows and painful with three hundred. selectinload fetches every tee in
    a single second query instead.
    """
    return list(
        session.scalars(
            select(Course).options(selectinload(Course.tees)).order_by(Course.name)
        ).all()
    )


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate, session: Session = Depends(get_session)
) -> Course:
    """Add a course and its tees together.

    201 Created rather than 200: the response says a new resource now exists,
    which is a different claim from "your request was processed".
    """
    course = Course(
        name=payload.name,
        city=payload.city,
        state=payload.state,
        tees=[
            # model_dump() rather than a field list: TeeCreate and Tee carry the
            # same column names, and spelling them out twice is how the four
            # nine-hole ratings got silently dropped the first time.
            Tee(**tee.model_dump())
            for tee in payload.tees
        ],
    )
    session.add(course)

    try:
        session.commit()
    except IntegrityError as exc:
        # The unique constraints are the source of truth here. Checking first
        # with a SELECT would still race two simultaneous requests; letting the
        # database decide and translating the error cannot.
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A course named {payload.name!r} already exists at that location, "
                "or two of the tees share a name."
            ),
        ) from exc

    session.refresh(course)
    return course


@router.post(
    "/{course_id}/tees",
    response_model=CourseRead,
    status_code=status.HTTP_201_CREATED,
)
def add_tees(
    course_id: int,
    payload: list[TeeCreate],
    session: Session = Depends(get_session),
) -> Course:
    """Add tees to a course that already exists.

    Courses were creatable only with their tees attached, and a course is unique
    on name and location -- so the second tee you ever played at a course was
    unreachable. You would meet that halfway through a backfill, at the first
    round played from a different set of tees, with no way past it. Hence this.

    Returns the whole course rather than the new tees, so a caller can replace
    its copy outright instead of merging one in and hoping the orders match.
    """
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No course with id {course_id}.",
        )

    for tee in payload:
        course.tees.append(Tee(**tee.model_dump()))

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"{course.name} already has a tee by that name. Tee names are "
                "unique per course."
            ),
        ) from exc

    session.refresh(course)
    return course


@router.patch("/{course_id}/tees/{tee_id}", response_model=CourseRead)
def update_tee(
    course_id: int,
    tee_id: int,
    payload: TeeUpdate,
    session: Session = Depends(get_session),
) -> Course:
    """Correct a tee's ratings — most often, add the nine-hole ones later.

    PATCH rather than PUT: the caller sends only what changes. Adding a front
    nine to a tee should not require re-sending its 18-hole figures, which is
    exactly the friction that pushed one real backfill into creating a second
    course instead.

    Changing a rating changes every past round played from this tee, because
    differentials are derived on read and never stored. That is the intended
    behaviour: a slope typed wrong has been quietly distorting history, and
    fixing it should fix the history too.

    The paired front/back check runs against the MERGED tee, not the payload —
    sending only a front slope for a tee that already has a front rating is a
    completion, not a half-filled state.
    """
    tee = session.get(Tee, tee_id)
    if tee is None or tee.course_id != course_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tee with id {tee_id} at course {course_id}.",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tee, field, value)

    for side in ("front", "back"):
        rating = getattr(tee, f"{side}_course_rating")
        slope = getattr(tee, f"{side}_slope_rating")
        if (rating is None) != (slope is None):
            session.rollback()
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{side}_course_rating and {side}_slope_rating must end up "
                    "either both set or both empty."
                ),
            )

    session.commit()
    course = session.get(Course, course_id)
    session.refresh(course)
    return course
