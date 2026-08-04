"""add updated_at to match_analysis_folder_items

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-08-05 09:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, Sequence[str], None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {
        col["name"] for col in inspector.get_columns("match_analysis_folder_items")
    }
    if "updated_at" not in existing:
        op.add_column(
            "match_analysis_folder_items",
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {
        col["name"] for col in inspector.get_columns("match_analysis_folder_items")
    }
    if "updated_at" in existing:
        op.drop_column("match_analysis_folder_items", "updated_at")
