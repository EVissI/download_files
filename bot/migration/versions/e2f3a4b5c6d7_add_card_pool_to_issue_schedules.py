"""add card_pool to content card issue schedules

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

content_card_pool_enum = sa.Enum(
    "cards",
    "pip_count",
    name="contentcardpool",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "content_card_issue_schedules",
        sa.Column(
            "card_pool",
            content_card_pool_enum,
            nullable=False,
            server_default="cards",
        ),
    )
    op.create_index(
        "ix_content_card_issue_schedules_card_pool",
        "content_card_issue_schedules",
        ["card_pool"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_content_card_issue_schedules_card_pool",
        table_name="content_card_issue_schedules",
    )
    op.drop_column("content_card_issue_schedules", "card_pool")
