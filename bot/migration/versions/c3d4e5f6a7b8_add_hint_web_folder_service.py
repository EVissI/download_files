"""add service scope to hint web folders

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-03 14:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hint_web_folders",
        sa.Column(
            "service",
            sa.String(length=20),
            nullable=False,
            server_default="hints",
        ),
    )
    op.create_index(
        "ix_hint_web_folders_service",
        "hint_web_folders",
        ["service"],
        unique=False,
    )
    op.drop_index(
        "ix_hint_web_folders_user_id_parent_id",
        table_name="hint_web_folders",
    )
    op.create_index(
        "ix_hint_web_folders_user_id_service_parent_id",
        "hint_web_folders",
        ["user_id", "service", "parent_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hint_web_folders_user_id_service_parent_id",
        table_name="hint_web_folders",
    )
    op.create_index(
        "ix_hint_web_folders_user_id_parent_id",
        "hint_web_folders",
        ["user_id", "parent_id"],
        unique=False,
    )
    op.drop_index("ix_hint_web_folders_service", table_name="hint_web_folders")
    op.drop_column("hint_web_folders", "service")
