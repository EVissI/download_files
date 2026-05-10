"""merge cards fullscreen flags into one field

Revision ID: 8a1b2c3d4e5f
Revises: 6f8a9b0c1d2e
Create Date: 2026-05-11 03:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "6f8a9b0c1d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_cards_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE webapp_settings
            SET webapp_fullscreen_cards_enabled =
                COALESCE(webapp_fullscreen_cards_cabinet_enabled, true)
                OR COALESCE(webapp_fullscreen_content_card_view_enabled, true)
            """
        )
    )
    op.drop_column("webapp_settings", "webapp_fullscreen_cards_cabinet_enabled")
    op.drop_column("webapp_settings", "webapp_fullscreen_content_card_view_enabled")


def downgrade() -> None:
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_cards_cabinet_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_content_card_view_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE webapp_settings
            SET
                webapp_fullscreen_cards_cabinet_enabled = COALESCE(webapp_fullscreen_cards_enabled, true),
                webapp_fullscreen_content_card_view_enabled = COALESCE(webapp_fullscreen_cards_enabled, true)
            """
        )
    )
    op.drop_column("webapp_settings", "webapp_fullscreen_cards_enabled")
