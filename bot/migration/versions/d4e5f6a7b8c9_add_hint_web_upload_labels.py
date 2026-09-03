"""add personal labels for hint/board web uploads

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-03 15:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hint_web_upload_labels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=False),
        sa.Column(
            "labels",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["web_users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["hint_viewer_web_uploads.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "upload_id",
            name="uq_hint_web_upload_labels_user_id_upload_id",
        ),
    )
    op.create_index(
        "ix_hint_web_upload_labels_user_id",
        "hint_web_upload_labels",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_hint_web_upload_labels_upload_id",
        "hint_web_upload_labels",
        ["upload_id"],
        unique=False,
    )

    op.create_table(
        "hint_web_label_presets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("service", sa.String(length=20), nullable=False, server_default="hints"),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["web_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "service",
            "value",
            name="uq_hint_web_label_presets_user_id_service_value",
        ),
    )
    op.create_index(
        "ix_hint_web_label_presets_user_id",
        "hint_web_label_presets",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_hint_web_label_presets_service",
        "hint_web_label_presets",
        ["service"],
        unique=False,
    )
    op.create_index(
        "ix_hint_web_label_presets_user_id_service",
        "hint_web_label_presets",
        ["user_id", "service"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hint_web_label_presets_user_id_service",
        table_name="hint_web_label_presets",
    )
    op.drop_index("ix_hint_web_label_presets_service", table_name="hint_web_label_presets")
    op.drop_index("ix_hint_web_label_presets_user_id", table_name="hint_web_label_presets")
    op.drop_table("hint_web_label_presets")
    op.drop_index(
        "ix_hint_web_upload_labels_upload_id",
        table_name="hint_web_upload_labels",
    )
    op.drop_index("ix_hint_web_upload_labels_user_id", table_name="hint_web_upload_labels")
    op.drop_table("hint_web_upload_labels")
