"""add service column to hint_viewer_web_uploads

Revision ID: w7x8y9z0a1b2
Revises: v6w7x8y9z0a1
Create Date: 2026-08-25 14:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w7x8y9z0a1b2"
down_revision: Union[str, Sequence[str], None] = "v6w7x8y9z0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hint_viewer_web_uploads",
        sa.Column(
            "service",
            sa.String(length=20),
            nullable=False,
            server_default="hints",
        ),
    )
    op.create_index(
        "ix_hint_viewer_web_uploads_service",
        "hint_viewer_web_uploads",
        ["service"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hint_viewer_web_uploads_service",
        table_name="hint_viewer_web_uploads",
    )
    op.drop_column("hint_viewer_web_uploads", "service")
