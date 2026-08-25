"""Shared FastAPI dependencies.

Currently one: who is making this request.

Authentication is build-order step 10, and until it lands there is exactly one
golfer. Rather than scatter that assumption through the routes, it lives behind
`get_current_user` -- so every route already asks "who is this?" and gets a real
`User` row back. When auth ships, this function starts verifying a token and
looking up the matching user, and no route changes.

That is the point of putting it here now: the alternative is routes that quietly
assume a single user, which then all have to be found and rewritten later.
"""

import os

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import User, get_session

# Overridable so a test or a second local profile can use a different row.
DEV_USER_EMAIL = os.getenv("DEV_USER_EMAIL", "dev@localhost")
DEV_USER_NAME = os.getenv("DEV_USER_NAME", "Dev Golfer")


def get_current_user(session: Session = Depends(get_session)) -> User:
    """The signed-in golfer. Until auth exists, a single row created on demand.

    Creating it here rather than in a seed script means a fresh database works
    on the first request, with no setup step to forget.
    """
    user = session.scalars(select(User).where(User.email == DEV_USER_EMAIL)).first()

    if user is None:
        user = User(email=DEV_USER_EMAIL, display_name=DEV_USER_NAME)
        session.add(user)
        session.commit()
        session.refresh(user)

    return user
