"""add user_promocode.expires_at

Revision ID: z0a1b2c3d4e5
Revises: y9z0a1b2c3d4
Create Date: 2026-09-01 15:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "y9z0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_promocode",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE user_promocode AS up
        SET expires_at = (up.created_at AT TIME ZONE 'UTC')
                         + (p.duration_days * INTERVAL '1 day')
        FROM promocode AS p
        WHERE up.promocode_id = p.id
          AND p.duration_days IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("user_promocode", "expires_at")
