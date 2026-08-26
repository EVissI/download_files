from datetime import datetime, timedelta, timezone

from flask import url_for
from flask_appbuilder import BaseView, expose, has_access
from loguru import logger
from sqlalchemy import func, select
from werkzeug.routing import BuildError

from bot.db.models import User, UserMatchAnalysis


def _user_id_background(last_at: datetime | None) -> str:
    if last_at is None:
        return "#ffe0b2"
    if last_at.tzinfo is None:
        last_at = last_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - last_at < timedelta(days=1):
        return "#c8e6c9"
    return "#ffe0b2"


class UsersWithMatchAnalysesView(BaseView):
    """Read-only: пользователи с выданными анализами матча."""

    route_base = "/users_with_match_analyses"
    default_view = "list"

    @expose("/")
    @has_access
    def list(self):
        rows = []
        try:
            stmt = (
                select(
                    User.id.label("user_id"),
                    User.username.label("username"),
                    User.admin_insert_name.label("admin_insert_name"),
                    func.count(UserMatchAnalysis.id).label("cards_count"),
                    func.max(UserMatchAnalysis.created_at).label("last_card_at"),
                )
                .join(UserMatchAnalysis, UserMatchAnalysis.user_id == User.id)
                .where(User.id > 0)
                .group_by(User.id, User.username, User.admin_insert_name)
                .order_by(func.count(UserMatchAnalysis.id).desc(), User.id.asc())
            )
            for item in self.appbuilder.session.execute(stmt).all():
                user_id = int(item.user_id)
                username = str(item.username).strip() if item.username else ""
                tg_username = f"@{username}" if username else "—"
                admin_name = (
                    str(item.admin_insert_name).strip()
                    if item.admin_insert_name
                    else "—"
                )
                try:
                    show_url = url_for("UserModelView.show", pk=str(user_id))
                except BuildError:
                    show_url = f"/admin/usermodelview/show/{user_id}"
                rows.append(
                    {
                        "user_id": user_id,
                        "user_id_bg": _user_id_background(item.last_card_at),
                        "tg_username": tg_username,
                        "admin_name": admin_name,
                        "cards_count": int(item.cards_count or 0),
                        "show_url": show_url,
                    }
                )
        except Exception as e:
            logger.exception("UsersWithMatchAnalysesView list error: {}", e)

        return self.render_template("users_with_match_analyses.html", rows=rows)
