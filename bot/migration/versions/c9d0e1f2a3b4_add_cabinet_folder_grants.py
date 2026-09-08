"""owner, shared flag and grants for cards / match-analysis folders

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-09 04:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_folder_share_columns(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column(
            "owner_user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        table_name,
        sa.Column(
            "is_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        f"ix_{table_name}_owner_user_id",
        table_name,
        ["owner_user_id"],
        unique=False,
    )


def _create_grant_table(
    table_name: str,
    folder_table: str,
    unique_name: str,
    user_index: str,
) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["folder_id"], [f"{folder_table}.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("folder_id", "user_id", name=unique_name),
    )
    op.create_index(user_index, table_name, ["user_id"], unique=False)


def upgrade() -> None:
    _add_folder_share_columns("content_card_folders")
    _add_folder_share_columns("match_analysis_folders")
    _create_grant_table(
        "content_card_folder_grants",
        "content_card_folders",
        "uq_content_card_folder_grants_folder_id_user_id",
        "ix_content_card_folder_grants_user_id",
    )
    _create_grant_table(
        "match_analysis_folder_grants",
        "match_analysis_folders",
        "uq_match_analysis_folder_grants_folder_id_user_id",
        "ix_match_analysis_folder_grants_user_id",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_match_analysis_folder_grants_user_id",
        table_name="match_analysis_folder_grants",
    )
    op.drop_table("match_analysis_folder_grants")
    op.drop_index(
        "ix_content_card_folder_grants_user_id",
        table_name="content_card_folder_grants",
    )
    op.drop_table("content_card_folder_grants")
    op.drop_index("ix_match_analysis_folders_owner_user_id", table_name="match_analysis_folders")
    op.drop_column("match_analysis_folders", "is_shared")
    op.drop_column("match_analysis_folders", "owner_user_id")
    op.drop_index("ix_content_card_folders_owner_user_id", table_name="content_card_folders")
    op.drop_column("content_card_folders", "is_shared")
    op.drop_column("content_card_folders", "owner_user_id")
