"""course uniqueness must treat blank locations as equal

The constraint on (name, city, state) has not been doing its job. Postgres
treats NULLs as distinct in a unique constraint by default, and city and state
are both optional -- so two courses with the same name and no location entered
did not collide. Adding the same course twice silently produced two rows and two
entries in the picker, which is exactly what happened in the first real backfill.

NULLS NOT DISTINCT is the Postgres 15+ answer: it makes two NULLs count as equal
for the purposes of the constraint.

This cannot be applied over data that already contains duplicates, so the
upgrade refuses rather than failing halfway with an opaque constraint violation.
Merging them is not something a migration should guess at -- rounds point at
tees, tees point at courses, and which duplicate is the keeper is a judgement.

Revision ID: 41d9006307fc
Revises: 96e239228af8
Create Date: 2026-08-28 03:39:06.718794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41d9006307fc'
down_revision: Union[str, Sequence[str], None] = '96e239228af8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    duplicates = op.get_bind().execute(
        sa.text(
            """
            SELECT name, count(*) AS n
            FROM courses
            GROUP BY name, city, state
            HAVING count(*) > 1
            """
        )
    ).all()
    if duplicates:
        listed = ", ".join(f"{name!r} x{n}" for name, n in duplicates)
        raise RuntimeError(
            "Duplicate courses already exist and the new constraint cannot be "
            f"applied over them: {listed}.\n"
            "Merge them by hand first -- move the tees worth keeping onto one "
            "course, repoint any rounds at the surviving tee, delete the "
            "leftover. See the cleanup recipe in README.md, then re-run."
        )

    op.drop_constraint(op.f('uq_course_name_location'), 'courses', type_='unique')
    op.create_unique_constraint('uq_course_name_location', 'courses', ['name', 'city', 'state'], postgresql_nulls_not_distinct=True)


def downgrade() -> None:
    """Downgrade schema. Restores the constraint that lets duplicates through."""
    op.drop_constraint('uq_course_name_location', 'courses', type_='unique')
    op.create_unique_constraint(op.f('uq_course_name_location'), 'courses', ['name', 'city', 'state'], postgresql_nulls_not_distinct=False)
