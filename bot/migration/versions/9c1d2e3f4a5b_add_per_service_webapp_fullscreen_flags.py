"""add per-service webapp fullscreen flags

Revision ID: 9c1d2e3f4a5b
Revises: b8d1c2e3f4a5
Create Date: 2026-05-08 15:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "b8d1c2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_hints_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_pokaz_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
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
    op.add_column(
        "webapp_settings",
        sa.Column(
            "webapp_fullscreen_admin_login_enabled",
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
                webapp_fullscreen_hints_enabled = webapp_fullscreen_enabled,
                webapp_fullscreen_pokaz_enabled = webapp_fullscreen_enabled,
                webapp_fullscreen_cards_cabinet_enabled = webapp_fullscreen_enabled,
                webapp_fullscreen_content_card_view_enabled = webapp_fullscreen_enabled,
                webapp_fullscreen_admin_login_enabled = webapp_fullscreen_enabled
            """
        )
    )


def downgrade() -> None:
    op.drop_column("webapp_settings", "webapp_fullscreen_admin_login_enabled")
    op.drop_column("webapp_settings", "webapp_fullscreen_content_card_view_enabled")
    op.drop_column("webapp_settings", "webapp_fullscreen_cards_cabinet_enabled")
    op.drop_column("webapp_settings", "webapp_fullscreen_pokaz_enabled")
    op.drop_column("webapp_settings", "webapp_fullscreen_hints_enabled")
