"""add_new_fileld

Revision ID: 193033b605bb
Revises: 74e45d0468ba
Create Date: 2025-08-19 18:13:39.449514

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "193033b605bb"
down_revision: Union[str, Sequence[str], None] = "74e45d0468ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Создаем новый ENUM тип
    new_enum = postgresql.ENUM(
        "MATCH", "MONEYGAME", "SHORT_BOARD", name="servicetype", create_type=False
    )
    new_enum.create(op.get_bind(), checkfirst=True)

    # Обновляем колонку с использованием явного преобразования
    op.execute(
        "ALTER TABLE analize_payment_service_quantities ALTER COLUMN service_type TYPE servicetype USING service_type::text::servicetype"
    )
    op.execute(
        "ALTER TABLE user_analize_payment_services ALTER COLUMN service_type TYPE servicetype USING service_type::text::servicetype"
    )

    # Удаляем старый ENUM тип, если он больше не используется
    op.execute("DROP TYPE IF EXISTS paymentservicetype")


def downgrade() -> None:
    """Downgrade schema."""
    # Создаем старый ENUM тип
    old_enum = postgresql.ENUM(
        "ANALYSIS", "SHORT_BOARD", name="paymentservicetype", create_type=False
    )
    old_enum.create(op.get_bind(), checkfirst=True)

    # Обновляем колонку обратно с использованием явного преобразования
    op.execute(
        "ALTER TABLE analize_payment_service_quantities ALTER COLUMN service_type TYPE paymentservicetype USING service_type::text::paymentservicetype"
    )
    op.execute(
        "ALTER TABLE user_analize_payment_services ALTER COLUMN service_type TYPE paymentservicetype USING service_type::text::paymentservicetype"
    )

    # Удаляем новый ENUM тип, если он больше не используется
    op.execute("DROP TYPE IF EXISTS servicetype")
