"""add schedules for hint/board web folders

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-03 16:25:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hint_web_folder_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column(
            "files_per_run",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("weekdays", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issue_time_msk", sa.String(length=5), nullable=False),
        sa.Column(
            "labels",
            postgresql.ARRAY(sa.String(length=255)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("scheduler_job_id", sa.String(length=128), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "folder_id", name="uq_hint_web_folder_schedules_folder_id"
        ),
        sa.UniqueConstraint("scheduler_job_id"),
    )


def downgrade() -> None:
    op.drop_table("hint_web_folder_schedules")
