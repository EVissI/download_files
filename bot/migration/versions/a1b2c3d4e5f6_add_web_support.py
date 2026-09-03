"""add web support chat tables

Revision ID: a1b2c3d4e5f6
Revises: z0a1b2c3d4e5
Create Date: 2026-09-03 10:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "z0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_support_threads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_preview", sa.String(length=240), nullable=True),
        sa.Column("last_author_role", sa.String(length=10), nullable=True),
        sa.Column("user_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_last_read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["web_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_web_support_threads_user_id",
        "web_support_threads",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_web_support_threads_last_message_at",
        "web_support_threads",
        ["last_message_at"],
    )

    op.create_table(
        "web_support_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("author_role", sa.String(length=10), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_path", sa.String(length=200), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["thread_id"], ["web_support_threads.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_web_support_messages_thread_id",
        "web_support_messages",
        ["thread_id"],
    )
    op.create_index(
        "ix_web_support_messages_author_user_id",
        "web_support_messages",
        ["author_user_id"],
    )

    op.create_table(
        "web_support_attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_name", sa.String(length=80), nullable=False),
        sa.Column("s3_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["message_id"], ["web_support_messages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_web_support_attachments_message_id",
        "web_support_attachments",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_support_attachments_message_id",
        table_name="web_support_attachments",
    )
    op.drop_table("web_support_attachments")
    op.drop_index(
        "ix_web_support_messages_author_user_id",
        table_name="web_support_messages",
    )
    op.drop_index(
        "ix_web_support_messages_thread_id",
        table_name="web_support_messages",
    )
    op.drop_table("web_support_messages")
    op.drop_index(
        "ix_web_support_threads_last_message_at",
        table_name="web_support_threads",
    )
    op.drop_index("ix_web_support_threads_user_id", table_name="web_support_threads")
    op.drop_table("web_support_threads")
