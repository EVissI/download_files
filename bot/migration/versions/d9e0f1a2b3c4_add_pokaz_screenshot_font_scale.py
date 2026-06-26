"""add pokaz screenshot font scale

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-06-07 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webapp_settings",
        sa.Column(
            "pokaz_screenshot_font_scale_percent",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("100"),
        ),
    )


def downgrade() -> None:
    op.drop_column("webapp_settings", "pokaz_screenshot_font_scale_percent")
