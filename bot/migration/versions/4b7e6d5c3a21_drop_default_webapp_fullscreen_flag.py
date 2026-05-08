"""drop default webapp fullscreen flag

Revision ID: 4b7e6d5c3a21
Revises: 9c1d2e3f4a5b
Create Date: 2026-05-08 18:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4b7e6d5c3a21"
down_revision: Union[str, Sequence[str], None] = "9c1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("webapp_settings", "webapp_fullscreen_enabled")


def downgrade() -> None:
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE webapp_settings
            SET webapp_fullscreen_enabled = COALESCE(webapp_fullscreen_hints_enabled, true)
            """
        )
    )
