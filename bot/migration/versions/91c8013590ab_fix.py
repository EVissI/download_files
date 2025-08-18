"""fix

Revision ID: 91c8013590ab
Revises: 9599b7d990ce
Create Date: 2025-08-18 21:54:01.042706

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM


# revision identifiers, used by Alembic.
revision: str = "91c8013590ab"
down_revision: Union[str, Sequence[str], None] = "9599b7d990ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Проверяем существование типа servicetype
    conn = op.get_bind()
    if not conn.dialect.has_type(conn, "servicetype"):
        servicetype_enum = ENUM(
            "ANALYSIS", "SHORT_BOARD", name="servicetype", create_type=False
        )
        servicetype_enum.create(conn)

    # Создаём таблицы
    op.create_table(
        "analize_payment_service_quantities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("analize_payment_id", sa.Integer(), nullable=False),
        sa.Column(
            "service_type",
            sa.Enum("ANALYSIS", "SHORT_BOARD", name="servicetype"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["analize_payment_id"], ["analize_payments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_analize_payment_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_analize_payment_id", sa.Integer(), nullable=False),
        sa.Column(
            "service_type",
            sa.Enum("ANALYSIS", "SHORT_BOARD", name="servicetype"),
            nullable=False,
        ),
        sa.Column("remaining_quantity", sa.Integer(), nullable=False),
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
            ["user_analize_payment_id"], ["user_analize_payments.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.drop_column("user_analize_payments", "current_analize_balance")


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем таблицы
    op.add_column(
        "user_analize_payments",
        sa.Column(
            "current_analize_balance", sa.INTEGER(), autoincrement=False, nullable=False
        ),
    )
    op.drop_table("user_analize_payment_services")
    op.drop_table("analize_payment_service_quantities")

    # Удаляем тип servicetype, если он больше не используется
    conn = op.get_bind()
    servicetype_enum = ENUM(
        "ANALYSIS", "SHORT_BOARD", name="servicetype", create_type=False
    )
    servicetype_enum.drop(conn, checkfirst=True)
