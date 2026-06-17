"""add content card pool (cards / pip_count)

Revision ID: d1e2f3a4b5c6
Revises: c8d9e0f1a2b3
Create Date: 2026-06-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

content_card_pool_enum = sa.Enum(
    "cards",
    "pip_count",
    name="contentcardpool",
)


def upgrade() -> None:
    content_card_pool_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "content_cards",
        sa.Column(
            "card_pool",
            content_card_pool_enum,
            nullable=False,
            server_default="cards",
        ),
    )
    op.create_index("ix_content_cards_card_pool", "content_cards", ["card_pool"])

    op.add_column(
        "content_card_folders",
        sa.Column(
            "folder_pool",
            content_card_pool_enum,
            nullable=False,
            server_default="cards",
        ),
    )
    op.create_index(
        "ix_content_card_folders_folder_pool_parent_id",
        "content_card_folders",
        ["folder_pool", "parent_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_card_folders_folder_pool_parent_id",
        table_name="content_card_folders",
    )
    op.drop_column("content_card_folders", "folder_pool")
    op.drop_index("ix_content_cards_card_pool", table_name="content_cards")
    op.drop_column("content_cards", "card_pool")
    content_card_pool_enum.drop(op.get_bind(), checkfirst=True)
