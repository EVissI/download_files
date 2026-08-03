"""add Base timestamps to match analysis grant tables

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-08-03 17:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, Sequence[str], None] = "l6m7n8o9p0q1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_timestamps_if_missing(table_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {col["name"] for col in inspector.get_columns(table_name)}
    if "created_at" not in existing:
        op.add_column(
            table_name,
            sa.Column(
                "created_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
    if "updated_at" not in existing:
        op.add_column(
            table_name,
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )


def upgrade() -> None:
    _add_timestamps_if_missing("user_match_analyses")
    _add_timestamps_if_missing("match_analysis_activation_links")


def downgrade() -> None:
    op.drop_column("match_analysis_activation_links", "updated_at")
    op.drop_column("match_analysis_activation_links", "created_at")
    op.drop_column("user_match_analyses", "updated_at")
    op.drop_column("user_match_analyses", "created_at")
