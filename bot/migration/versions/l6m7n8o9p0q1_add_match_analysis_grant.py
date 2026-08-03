"""match analysis grant: pool, ownership, activation links, is_ready

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-08-03 10:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l6m7n8o9p0q1"
down_revision: Union[str, Sequence[str], None] = "k5l6m7n8o9p0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL: ADD VALUE нельзя в обычной транзакции на старых версиях —
    # autocommit_block безопаснее.
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE contentcardpool ADD VALUE IF NOT EXISTS 'match_analysis'"
        )

    op.add_column(
        "promocode",
        sa.Column(
            "card_pool",
            postgresql.ENUM(
                "cards",
                "pip_count",
                "match_analysis",
                name="contentcardpool",
                create_type=False,
            ),
            nullable=False,
            server_default="cards",
        ),
    )
    op.create_index("ix_promocode_card_pool", "promocode", ["card_pool"])

    op.add_column(
        "match_analyses",
        sa.Column(
            "is_ready",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_table(
        "user_match_analyses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("match_analysis_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["match_analysis_id"], ["match_analyses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "match_analysis_id",
            name="uq_user_match_analyses_user_id_match_analysis_id",
        ),
    )
    op.create_index(
        "ix_user_match_analyses_user_id", "user_match_analyses", ["user_id"]
    )
    op.create_index(
        "ix_user_match_analyses_match_analysis_id",
        "user_match_analyses",
        ["match_analysis_id"],
    )

    status_enum = postgresql.ENUM(
        "unactivate",
        "activate",
        name="matchanalysislinkstatus",
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "match_analysis_activation_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("link", sa.String(length=128), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "unactivate",
                "activate",
                name="matchanalysislinkstatus",
                create_type=False,
            ),
            nullable=False,
            server_default="unactivate",
        ),
        sa.Column(
            "match_analysis_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
    op.drop_table("match_analysis_activation_links")
    postgresql.ENUM(
        "unactivate",
        "activate",
        name="matchanalysislinkstatus",
    ).drop(op.get_bind(), checkfirst=True)

    op.drop_index(
        "ix_user_match_analyses_match_analysis_id",
        table_name="user_match_analyses",
    )
    op.drop_index("ix_user_match_analyses_user_id", table_name="user_match_analyses")
    op.drop_table("user_match_analyses")

    op.drop_column("match_analyses", "is_ready")

    op.drop_index("ix_promocode_card_pool", table_name="promocode")
    op.drop_column("promocode", "card_pool")
    # Значение enum contentcardpool.match_analysis не удаляем (PostgreSQL ограничение).
