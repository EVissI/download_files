from datetime import datetime, timedelta, timezone

from flask import url_for
from flask_appbuilder import BaseView, expose, has_access
from loguru import logger
from sqlalchemy import func, select
from werkzeug.routing import BuildError

from bot.db.models import ContentCard, ContentCardPool, User, UserContentCard


def _user_id_background(last_card_at: datetime | None) -> str:
    if last_card_at is None:
        return "#ffe0b2"
    if last_card_at.tzinfo is None:
        last_card_at = last_card_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - last_card_at < timedelta(days=1):
        return "#c8e6c9"
    return "#ffe0b2"


class UsersWithPipCountCardsView(BaseView):
    """Read-only: пользователи с выданными карточками пула «Подсчёт пипсов»."""

    route_base = "/users_with_pip_count_cards"
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
                    func.count(UserContentCard.id).label("cards_count"),
                    func.max(UserContentCard.created_at).label("last_card_at"),
                )
                .join(UserContentCard, UserContentCard.user_id == User.id)
                .join(ContentCard, ContentCard.id == UserContentCard.content_card_id)
                .where(ContentCard.card_pool == ContentCardPool.PIP_COUNT.value)
                .group_by(User.id, User.username, User.admin_insert_name)
                .order_by(func.count(UserContentCard.id).desc(), User.id.asc())
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
            logger.exception("UsersWithPipCountCardsView list error: {}", e)

        return self.render_template("users_with_pip_count_cards.html", rows=rows)
