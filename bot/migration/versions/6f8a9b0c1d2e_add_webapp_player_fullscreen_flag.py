"""add webapp player fullscreen flag

Revision ID: 6f8a9b0c1d2e
Revises: 4b7e6d5c3a21
Create Date: 2026-05-08 18:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f8a9b0c1d2e"
down_revision: Union[str, Sequence[str], None] = "4b7e6d5c3a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_player_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("webapp_settings", "webapp_fullscreen_player_enabled")
