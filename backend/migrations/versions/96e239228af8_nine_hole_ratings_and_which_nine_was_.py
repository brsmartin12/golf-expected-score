"""nine hole ratings and which nine was played

Nine-hole rounds were stored but never graded: the tees table holds 18-hole
figures, and running half a round through them produces a differential several
strokes too low. This adds what is needed to do it properly.

  tees.front_/back_course_rating, tees.front_/back_slope_rating
      The USGA publishes all four per tee. The slope is why both nines are
      stored separately rather than one shared figure: halving the 18-hole
      Course Rating is accurate to about a tenth of a stroke, but the two nines'
      slopes routinely differ by several points. Nullable, because a tee without
      them still works -- its nines are left out of the quantiles instead.

  rounds.nine  ('front' | 'back' | NULL)
      Replaces the is_nine_hole boolean. Which nine is not optional information
      once the two are rated separately, and one nullable column makes
      "nine holes, side unknown" unstorable.

That last point is why the upgrade below refuses to run rather than dropping
is_nine_hole outright. A row flagged as nine holes has no recorded side, so it
cannot be converted; dropping the flag would silently reclassify it as a full
round and feed half a score into the 18-hole population. The guard turns that
into a stop with instructions.

Revision ID: 96e239228af8
Revises: f0af46a77733
Create Date: 2026-08-26 13:55:46.570096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96e239228af8'
down_revision: Union[str, Sequence[str], None] = 'f0af46a77733'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('rounds', sa.Column('nine', sa.String(length=5), nullable=True))
    op.create_check_constraint('ck_round_nine_is_front_or_back', 'rounds', "nine IS NULL OR nine IN ('front', 'back')")

    # Refuse to guess which nine an existing nine-hole round was played on.
    # Guessing wrong picks the wrong Course Rating and Slope; dropping the flag
    # silently promotes half a round to a full one. Neither is acceptable
    # without the operator's say-so, so stop and say what to do.
    stranded = op.get_bind().execute(
        sa.text("SELECT count(*) FROM rounds WHERE is_nine_hole")
    ).scalar_one()
    if stranded:
        raise RuntimeError(
            f"{stranded} nine-hole round(s) predate this migration and have no "
            "recorded side. Set it by hand before upgrading, e.g.\n"
            "    UPDATE rounds SET nine = 'front' WHERE is_nine_hole AND id = ...;\n"
            "then re-run. Rounds already updated are matched on the new column, "
            "so this check will pass once every flagged row has a side."
        )

    op.drop_column('rounds', 'is_nine_hole')
    op.add_column('tees', sa.Column('front_course_rating', sa.Numeric(precision=4, scale=1), nullable=True))
    op.add_column('tees', sa.Column('front_slope_rating', sa.Integer(), nullable=True))
    op.add_column('tees', sa.Column('back_course_rating', sa.Numeric(precision=4, scale=1), nullable=True))
    op.add_column('tees', sa.Column('back_slope_rating', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_tee_back_nine_complete', 'tees', '(back_course_rating IS NULL) = (back_slope_rating IS NULL)')
    op.create_check_constraint('ck_tee_back_slope_in_whs_range', 'tees', 'back_slope_rating IS NULL OR back_slope_rating BETWEEN 55 AND 155')
    op.create_check_constraint('ck_tee_front_nine_complete', 'tees', '(front_course_rating IS NULL) = (front_slope_rating IS NULL)')
    op.create_check_constraint('ck_tee_front_slope_in_whs_range', 'tees', 'front_slope_rating IS NULL OR front_slope_rating BETWEEN 55 AND 155')


def downgrade() -> None:
    """Downgrade schema.

    Destructive in one direction that cannot be helped: the four nine-hole
    ratings are dropped, and `nine` collapses back to a boolean, so which side
    was played is lost even though it was recorded.
    """
    op.drop_constraint('ck_tee_front_slope_in_whs_range', 'tees', type_='check')
    op.drop_constraint('ck_tee_front_nine_complete', 'tees', type_='check')
    op.drop_constraint('ck_tee_back_slope_in_whs_range', 'tees', type_='check')
    op.drop_constraint('ck_tee_back_nine_complete', 'tees', type_='check')
    op.drop_column('tees', 'back_slope_rating')
    op.drop_column('tees', 'back_course_rating')
    op.drop_column('tees', 'front_slope_rating')
    op.drop_column('tees', 'front_course_rating')
    op.add_column('rounds', sa.Column('is_nine_hole', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=False))
    op.execute("UPDATE rounds SET is_nine_hole = true WHERE nine IS NOT NULL")
    op.drop_constraint('ck_round_nine_is_front_or_back', 'rounds', type_='check')
    op.drop_column('rounds', 'nine')
