"""add content_card_activation_links table

Revision ID: e1a2b3c4d5e6
Revises: d8e9f0a1b2c3
Create Date: 2026-04-30 11:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d8e9f0a1b2c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    status_enum = postgresql.ENUM(
        "unactivate",
        "activate",
        name="contentcardlinkstatus",
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "content_card_activation_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("link", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            sa.Enum("unactivate", "activate", name="contentcardlinkstatus"),
            nullable=False,
            server_default="unactivate",
        ),
        sa.Column("card_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("link"),
    )


def downgrade() -> None:
    op.drop_table("content_card_activation_links")
    postgresql.ENUM(
        "unactivate",
        "activate",
        name="contentcardlinkstatus",
    ).drop(op.get_bind(), checkfirst=True)
