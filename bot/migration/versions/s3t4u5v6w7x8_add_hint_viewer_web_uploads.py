"""add hint_viewer_web_uploads table

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-08-24 05:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s3t4u5v6w7x8"
down_revision: Union[str, Sequence[str], None] = "r2s3t4u5v6w7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hint_viewer_web_uploads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.String(length=80), nullable=True),
        sa.Column("batch_id", sa.String(length=80), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("red_player", sa.String(length=100), nullable=True),
        sa.Column("black_player", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hint_viewer_web_uploads_user_id",
        "hint_viewer_web_uploads",
        ["user_id"],
    )
    op.create_index(
        "ix_hint_viewer_web_uploads_session_id",
        "hint_viewer_web_uploads",
        ["session_id"],
    )
    op.create_index(
        "ix_hint_viewer_web_uploads_game_id",
        "hint_viewer_web_uploads",
        ["game_id"],
    )
    op.create_index(
        "ix_hint_viewer_web_uploads_batch_id",
        "hint_viewer_web_uploads",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_hint_viewer_web_uploads_batch_id", table_name="hint_viewer_web_uploads")
    op.drop_index("ix_hint_viewer_web_uploads_game_id", table_name="hint_viewer_web_uploads")
    op.drop_index(
        "ix_hint_viewer_web_uploads_session_id", table_name="hint_viewer_web_uploads"
    )
    op.drop_index("ix_hint_viewer_web_uploads_user_id", table_name="hint_viewer_web_uploads")
    op.drop_table("hint_viewer_web_uploads")
