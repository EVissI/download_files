"""add created_at to hint_web_upload_labels (Base mixin)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-03 16:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"] for column in sa.inspect(bind).get_columns("hint_web_upload_labels")
    }
    if "created_at" not in existing:
        op.add_column(
            "hint_web_upload_labels",
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"] for column in sa.inspect(bind).get_columns("hint_web_upload_labels")
    }
    if "created_at" in existing:
        op.drop_column("hint_web_upload_labels", "created_at")
