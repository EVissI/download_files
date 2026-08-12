"""backfill user_match_analyses for creators

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-08-13 09:10:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "p0q1r2s3t4u5"
down_revision: Union[str, Sequence[str], None] = "o9p0q1r2s3t4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Выдаём создателям уже сохранённые анализы, чтобы они остались в кабинете."""
    op.execute(
        """
        INSERT INTO user_match_analyses (user_id, match_analysis_id, card_status)
        SELECT ma.created_by_user_id, ma.id, 'UNVIEWED'
        FROM match_analyses AS ma
        WHERE ma.created_by_user_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM user_match_analyses AS uma
              WHERE uma.user_id = ma.created_by_user_id
                AND uma.match_analysis_id = ma.id
          )
        """
    )


def downgrade() -> None:
    # Обратный откат неоднозначен: не удаляем выдачи, созданные вручную.
    pass
