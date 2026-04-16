"""add user content card status

Revision ID: a9f1c2d4e6b7
Revises: 48d1e7f79cd8
Create Date: 2026-04-16 10:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a9f1c2d4e6b7"
down_revision: Union[str, Sequence[str], None] = "48d1e7f79cd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    status_enum = postgresql.ENUM(
        "UNVIEWED",
        "VIEWED",
        "SOLVED",
        "FAVORITE",
        "HARD",
        name="usercontentcardstatus",
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "user_content_cards",
        sa.Column(
            "card_status",
            sa.Enum(
                "UNVIEWED",
                "VIEWED",
                "SOLVED",
                "FAVORITE",
                "HARD",
                name="usercontentcardstatus",
            ),
            nullable=False,
            server_default="UNVIEWED",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_content_cards", "card_status")
    postgresql.ENUM(
        "UNVIEWED",
        "VIEWED",
        "SOLVED",
        "FAVORITE",
        "HARD",
        name="usercontentcardstatus",
    ).drop(op.get_bind(), checkfirst=True)
