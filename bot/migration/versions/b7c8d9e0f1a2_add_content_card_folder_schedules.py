"""add content card folder schedules

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-06-07 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_card_folder_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column("cards_per_run", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("weekdays", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issue_time_msk", sa.String(length=5), nullable=False),
        sa.Column(
            "labels",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
        ),
        sa.Column("scheduler_job_id", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=True),
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
            ["content_card_folders.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("folder_id", name="uq_content_card_folder_schedules_folder_id"),
        sa.UniqueConstraint("scheduler_job_id"),
    )


def downgrade() -> None:
    op.drop_table("content_card_folder_schedules")
