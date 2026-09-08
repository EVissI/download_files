"""web analyze player stats journal

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-09 04:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_analyze_player_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("web_user_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(length=100), nullable=False),
        sa.Column("player_name_norm", sa.String(length=100), nullable=False),
        sa.Column("game_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("moves_marked_bad", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "moves_marked_very_bad", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("error_rate_chequer", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "chequerplay_rating",
            sa.String(length=50),
            nullable=False,
            server_default="",
        ),
        sa.Column(
            "rolls_marked_very_lucky", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("rolls_marked_lucky", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "rolls_marked_unlucky", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "rolls_marked_very_unlucky",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("rolls_rate_chequer", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "luck_rating", sa.String(length=50), nullable=False, server_default=""
        ),
        sa.Column(
            "missed_doubles_below_cp", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "missed_doubles_above_cp", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "wrong_doubles_below_sp", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column(
            "wrong_doubles_above_tg", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("wrong_takes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("wrong_passes", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cube_error_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "cube_decision_rating",
            sa.String(length=50),
            nullable=False,
            server_default="",
        ),
        sa.Column("snowie_error_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "overall_rating", sa.String(length=50), nullable=False, server_default=""
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["web_user_id"], ["web_users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "game_id",
            "player_name_norm",
            name="uq_web_analyze_player_stats_game_id_player_name_norm",
        ),
    )
    op.create_index(
        "ix_web_analyze_player_stats_web_user_id",
        "web_analyze_player_stats",
        ["web_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_web_analyze_player_stats_player_name_norm",
        "web_analyze_player_stats",
        ["player_name_norm"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_web_analyze_player_stats_player_name_norm",
        table_name="web_analyze_player_stats",
    )
    op.drop_index(
        "ix_web_analyze_player_stats_web_user_id",
        table_name="web_analyze_player_stats",
    )
    op.drop_table("web_analyze_player_stats")
