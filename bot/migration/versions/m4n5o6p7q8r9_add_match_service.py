"""add hints_game_id for match service

Revision ID: m4n5o6p7q8r9
Revises: d4c5b6a7e8f9
"""

from alembic import op
import sqlalchemy as sa

revision = "m4n5o6p7q8r9"
down_revision = "d4c5b6a7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hint_viewer_web_uploads",
        sa.Column("hints_game_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_hint_viewer_web_uploads_hints_game_id",
        "hint_viewer_web_uploads",
        ["hints_game_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hint_viewer_web_uploads_hints_game_id",
        table_name="hint_viewer_web_uploads",
    )
    op.drop_column("hint_viewer_web_uploads", "hints_game_id")
