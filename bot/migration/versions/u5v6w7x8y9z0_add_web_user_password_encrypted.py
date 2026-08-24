"""add web_users.password_encrypted

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-08-25 08:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u5v6w7x8y9z0"
down_revision: Union[str, Sequence[str], None] = "t4u5v6w7x8y9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "web_users",
        sa.Column("password_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("web_users", "password_encrypted")
