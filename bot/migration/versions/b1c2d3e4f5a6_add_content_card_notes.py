"""add content card notes

Revision ID: b1c2d3e4f5a6
Revises: a9f1c2d4e6b7
Create Date: 2026-04-16 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a9f1c2d4e6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("content_cards", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("content_cards", "notes")
