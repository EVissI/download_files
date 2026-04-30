"""add webapp_settings table

Revision ID: b8d1c2e3f4a5
Revises: a7c9e1f2b3d4
Create Date: 2026-05-01 08:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8d1c2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "a7c9e1f2b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webapp_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("webapp_fullscreen_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO webapp_settings (webapp_fullscreen_enabled) VALUES (true)"
        )
    )


def downgrade() -> None:
    op.drop_table("webapp_settings")
