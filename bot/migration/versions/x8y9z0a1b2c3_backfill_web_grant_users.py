"""backfill shadow users for web_users (id = -web_users.id)

Revision ID: x8y9z0a1b2c3
Revises: w7x8y9z0a1b2
Create Date: 2026-08-26 16:50:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x8y9z0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "w7x8y9z0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, login FROM web_users")).fetchall()
    for web_id, login in rows:
        grant_id = -int(web_id)
        exists = conn.execute(
            sa.text("SELECT 1 FROM users WHERE id = :id"),
            {"id": grant_id},
        ).scalar()
        if exists:
            continue
        username = f"web:{login or f'id{web_id}'}"[:80]
        conn.execute(
            sa.text(
                """
                INSERT INTO users (id, username, first_name, lang_code, role, created_at, updated_at)
                VALUES (
                    :id, :username, :first_name, 'ru', 'user',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {
                "id": grant_id,
                "username": username,
                "first_name": login,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM users
            WHERE id < 0
              AND username LIKE 'web:%'
            """
        )
    )
