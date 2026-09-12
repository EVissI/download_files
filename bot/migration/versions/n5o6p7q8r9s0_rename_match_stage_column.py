"""rename hints_game_id -> analyze_game_id for match service

Порядок стадий изменился: первым идёт разбор ошибок во внешнем воркере
(его id теперь в game_id), анализ считается на сервере после ответа воркера.

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
"""

from alembic import op

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM hint_viewer_web_uploads WHERE service = 'match'")
    op.alter_column(
        "hint_viewer_web_uploads",
        "hints_game_id",
        new_column_name="analyze_game_id",
    )
    op.execute(
        "ALTER INDEX IF EXISTS ix_hint_viewer_web_uploads_hints_game_id "
        "RENAME TO ix_hint_viewer_web_uploads_analyze_game_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER INDEX IF EXISTS ix_hint_viewer_web_uploads_analyze_game_id "
        "RENAME TO ix_hint_viewer_web_uploads_hints_game_id"
    )
    op.alter_column(
        "hint_viewer_web_uploads",
        "analyze_game_id",
        new_column_name="hints_game_id",
    )
