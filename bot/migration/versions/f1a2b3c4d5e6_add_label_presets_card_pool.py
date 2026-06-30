"""add card_pool to label_presets

Revision ID: f1a2b3c4d5e6
Revises: d9e0f1a2b3c4
Create Date: 2026-07-01 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
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
        "label_presets",
        sa.Column(
            "card_pool",
            content_card_pool_enum,
            nullable=False,
            server_default="cards",
        ),
    )
    op.drop_constraint("uq_label_presets_value", "label_presets", type_="unique")
    op.create_unique_constraint(
        "uq_label_presets_pool_value",
        "label_presets",
        ["card_pool", "value"],
    )
    op.create_index("ix_label_presets_card_pool", "label_presets", ["card_pool"])


def downgrade() -> None:
    op.drop_index("ix_label_presets_card_pool", table_name="label_presets")
    op.drop_constraint("uq_label_presets_pool_value", "label_presets", type_="unique")
    op.create_unique_constraint("uq_label_presets_value", "label_presets", ["value"])
    op.drop_column("label_presets", "card_pool")
