"""add web_users and rebind hint_viewer_web_uploads.user_id

Revision ID: t4u5v6w7x8y9
Revises: s3t4u5v6w7x8
Create Date: 2026-08-25 06:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t4u5v6w7x8y9"
down_revision: Union[str, Sequence[str], None] = "s3t4u5v6w7x8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_web_users_login", "web_users", ["login"], unique=True)

    op.execute("UPDATE hint_viewer_web_uploads SET user_id = NULL")
    op.drop_constraint(
        "hint_viewer_web_uploads_user_id_fkey",
        "hint_viewer_web_uploads",
        type_="foreignkey",
    )
    op.alter_column(
        "hint_viewer_web_uploads",
        "user_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.create_foreign_key(
        "hint_viewer_web_uploads_user_id_fkey",
        "hint_viewer_web_uploads",
        "web_users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute("UPDATE hint_viewer_web_uploads SET user_id = NULL")
    op.drop_constraint(
        "hint_viewer_web_uploads_user_id_fkey",
        "hint_viewer_web_uploads",
        type_="foreignkey",
    )
    op.alter_column(
        "hint_viewer_web_uploads",
        "user_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.create_foreign_key(
        "hint_viewer_web_uploads_user_id_fkey",
        "hint_viewer_web_uploads",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_index("ix_web_users_login", table_name="web_users")
    op.drop_table("web_users")
