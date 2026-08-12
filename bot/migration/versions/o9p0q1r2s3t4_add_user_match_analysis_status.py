"""add card_status to user_match_analyses

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-08-13 06:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "o9p0q1r2s3t4"
down_revision: Union[str, Sequence[str], None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = postgresql.ENUM(
        "UNVIEWED",
        "VIEWED",
        "SOLVED",
        "FAVORITE",
        "HARD",
        name="usercontentcardstatus",
        create_type=False,
    )
    op.add_column(
        "user_match_analyses",
        sa.Column(
            "card_status",
            status_enum,
            nullable=False,
            server_default="UNVIEWED",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_match_analyses", "card_status")
