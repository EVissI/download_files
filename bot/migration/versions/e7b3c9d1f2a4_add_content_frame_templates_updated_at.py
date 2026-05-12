"""add updated_at to content_frame_templates (Base mixin)

Revision ID: e7b3c9d1f2a4
Revises: c4f8a2e1b9d0
Create Date: 2026-05-12

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b3c9d1f2a4"
down_revision: Union[str, Sequence[str], None] = "c4f8a2e1b9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content_frame_templates",
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("content_frame_templates", "updated_at")
