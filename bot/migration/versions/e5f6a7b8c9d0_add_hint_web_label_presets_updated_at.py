"""add updated_at to hint_web_label_presets (Base mixin)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-03 16:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"] for column in sa.inspect(bind).get_columns("hint_web_label_presets")
    }
    if "updated_at" not in existing:
        op.add_column(
            "hint_web_label_presets",
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"] for column in sa.inspect(bind).get_columns("hint_web_label_presets")
    }
    if "updated_at" in existing:
        op.drop_column("hint_web_label_presets", "updated_at")
