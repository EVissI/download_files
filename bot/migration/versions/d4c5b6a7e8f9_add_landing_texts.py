"""add landing_texts

Revision ID: d4c5b6a7e8f9
Revises: e1f2a3b4c5d6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4c5b6a7e8f9"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "landing_texts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "page", sa.String(length=40), server_default="landing", nullable=False
        ),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("style_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page", "key", name="uq_landing_texts_page_key"),
    )


def downgrade() -> None:
    op.drop_table("landing_texts")
