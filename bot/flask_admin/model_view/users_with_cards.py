from flask import url_for
from flask_appbuilder import BaseView, expose, has_access
from loguru import logger
from sqlalchemy import func, select
from werkzeug.routing import BuildError

from bot.db.models import User, UserContentCard


class UsersWithCardsView(BaseView):
    """
    Read-only список пользователей, у которых есть карточки.
    """

    route_base = "/users_with_cards"
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
                    func.count(UserContentCard.id).label("cards_count"),
                )
                .join(UserContentCard, UserContentCard.user_id == User.id)
                .group_by(User.id, User.username)
                .order_by(func.count(UserContentCard.id).desc(), User.id.asc())
            )
            for item in self.appbuilder.session.execute(stmt).all():
                user_id = int(item.user_id)
                username = str(item.username).strip() if item.username else ""
                tg_username = f"@{username}" if username else "—"
                try:
                    show_url = url_for("UserModelView.show", pk=str(user_id))
                except BuildError:
                    show_url = f"/admin/usermodelview/show/{user_id}"
                rows.append(
                    {
                        "user_id": user_id,
                        "tg_username": tg_username,
                        "cards_count": int(item.cards_count or 0),
                        "show_url": show_url,
                    }
                )
        except Exception as e:
            logger.exception("UsersWithCardsView list error: {}", e)

        return self.render_template("users_with_cards.html", rows=rows)

