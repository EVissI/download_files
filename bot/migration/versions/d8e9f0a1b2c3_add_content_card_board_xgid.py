"""add content_cards.board_xgid

Revision ID: d8e9f0a1b2c3
Revises: c7e8f9a0b1c2
Create Date: 2026-04-28 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "content_cards",
        sa.Column("board_xgid", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("content_cards", "board_xgid")
