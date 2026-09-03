"""add personal hint web folders

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-03 13:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hint_web_folders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
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
            ["parent_id"],
            ["hint_web_folders.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hint_web_folders_user_id",
        "hint_web_folders",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_hint_web_folders_user_id_parent_id",
        "hint_web_folders",
        ["user_id", "parent_id"],
        unique=False,
    )

    op.create_table(
        "hint_web_folder_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"],
            ["hint_web_folders.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["hint_viewer_web_uploads.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "folder_id",
            "upload_id",
            name="uq_hint_web_folder_items_folder_id_upload_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("hint_web_folder_items")
    op.drop_index(
        "ix_hint_web_folders_user_id_parent_id",
        table_name="hint_web_folders",
    )
    op.drop_index("ix_hint_web_folders_user_id", table_name="hint_web_folders")
    op.drop_table("hint_web_folders")
