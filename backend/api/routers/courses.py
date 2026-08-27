"""Courses and their tees.

Read-heavy: this is what the course picker renders, and what both the
before-round and after-round screens need before they can say anything.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from api.schemas import CourseCreate, CourseRead, TeeCreate
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
