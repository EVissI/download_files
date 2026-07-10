from flask import Flask, url_for
from flask_appbuilder import AppBuilder, IndexView, ModelView, expose
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
import logging

from bot.flask_admin.model_view.content_cards import ContentCardModelView, PipCountContentCardModelView
from bot.flask_admin.model_view.content_card_issue_schedule import (
    ContentCardIssueScheduleModelView,
)
from bot.flask_admin.model_view.message_for_new import MessageForNewModelView
from bot.flask_admin.model_view.message_texts import MessagesTextsModelView
from bot.flask_admin.model_view.payment import (
    AnalizePaymentModelView,
    AnalizePaymentServiceQuantityInline,
)
from bot.flask_admin.model_view.promo import (
    PromocodeModelView,
    PromocodeServiceQuantityInline,
)
from bot.flask_admin.model_view.user import (
    UserModelView,
    UserPromocodeInline,
    UserAnalizePaymentInline,
)
from bot.flask_admin.model_view.user_group import FabUserGroupsModelView
from bot.flask_admin.model_view.users_with_cards import UsersWithCardsView
from bot.flask_admin.model_view.users_with_pip_count_cards import UsersWithPipCountCardsView
from bot.flask_admin.model_view.telegram_proxy import TelegramProxyModelView
from bot.flask_admin.model_view.webapp_settings import WebAppSettingsModelView

logger = logging.getLogger(__name__)

from bot.config import settings


# === СИНХРОННАЯ БД ДЛЯ FLASK-APPBUILDER ===
db = SQLAlchemy()


class CustomIndexView(IndexView):
    """Кастомная главная страница"""

    title = "Dashboard"

    @staticmethod
    def _menu_val(item, key, default=None):
        if isinstance(item, dict):
            return item.get(key, default)
        return getattr(item, key, default)

    @classmethod
    def _menu_href(cls, item):
        for key in ("href", "url", "link", "base_url"):
            val = cls._menu_val(item, key)
            if not isinstance(val, str):
                continue
            v = val.strip()
            if not v or v == "#" or v.lower().startswith("javascript"):
                continue
            return v
        return None

    @classmethod
    def _normalize_menu(cls, menu_data):
        out = []
        for item in menu_data or []:
            name = cls._menu_val(item, "name") or "Раздел"
            icon = cls._menu_val(item, "icon")
            children_raw = cls._menu_val(item, "childs") or cls._menu_val(item, "children") or []
            children = []
            for ch in children_raw:
                ch_name = cls._menu_val(ch, "name") or "Пункт"
                ch_href = cls._menu_href(ch)
                children.append({"name": ch_name, "href": ch_href})
            href = cls._menu_href(item) or (children[0]["href"] if children and children[0]["href"] else None)
            out.append({"name": name, "icon": icon, "href": href, "children": children})
        return out

    @expose("/")
    def index(self):
        menu_data = []
        try:
            menu_data = self.appbuilder.menu.get_data() or []
        except Exception as e:
            logger.warning(f"Failed to load FAB menu data for welcome page: {e}")

        login_url = "/login/"
        logout_url = "/logout/"
        try:
            login_url = url_for("AuthDBView.login")
        except Exception:
            pass
        try:
            logout_url = url_for("AuthDBView.logout")
        except Exception:
            pass

        return self.render_template(
            "fab_welcome.html",
            nav_sections=self._normalize_menu(menu_data),
            login_url=login_url,
            logout_url=logout_url,
        )


def create_app():
    """Создание Flask-AppBuilder приложения с аутентификацией"""

    app = Flask(__name__)

    # === КОНФИГУРАЦИЯ ===
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DB_URL.replace(
        "+asyncpg", ""
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["WTF_CSRF_ENABLED"] = True

    # === FLASK-APPBUILDER КОНФИГ ===
    app.config["FLASK_APP_BUILDER"] = {
        "THEME": "mybase.html",
        "ROWS_PER_PAGE": 20,
        "UPLOAD_FOLDER": "temp/admin_uploads",
        "BABEL_DEFAULT_LOCALE": "ru",
        "BABEL_DEFAULT_TIMEZONE": "Europe/Moscow",
    }
    db.init_app(app)

    with app.app_context():
        try:
            appbuilder = AppBuilder(app, db.session, indexview=CustomIndexView)
            db.create_all()
            register_models(appbuilder, db)
            logger.info("Flask admin initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Flask admin: {e}", exc_info=True)
            raise

    return app, appbuilder


def register_models(appbuilder, db):
    """Регистрация моделей в админ-панели"""

    appbuilder.add_view_no_menu(PromocodeServiceQuantityInline)
    appbuilder.add_view(
        PromocodeModelView,
        "Промокоды",
        icon="fa-gift",
    )
    appbuilder.add_view_no_menu(AnalizePaymentServiceQuantityInline)
    appbuilder.add_view(AnalizePaymentModelView, "Пакеты", icon="fa-credit-card")
    appbuilder.add_view_no_menu(UserPromocodeInline)
    appbuilder.add_view_no_menu(UserAnalizePaymentInline)
    appbuilder.add_view(UserModelView, "Пользователи", icon="fa-users")
    appbuilder.add_view(
        FabUserGroupsModelView,
        "Группы пользователей",
        icon="fa-object-group",
    )
    appbuilder.add_view(
        MessageForNewModelView, "Сообщения для новеньких", icon="fa-calendar-o"
    )
    appbuilder.add_view(MessagesTextsModelView, "Текстовки", icon="fa-comment")
    appbuilder.add_view(
        WebAppSettingsModelView,
        "Настройки WebApp",
        icon="fa-cog",
    )
    appbuilder.add_view(
        TelegramProxyModelView,
        "Прокси Telegram",
        icon="fa-random",
    )
    appbuilder.add_view(ContentCardModelView, "Карточки", icon="fa-clone")
    appbuilder.add_view(
        PipCountContentCardModelView,
        "Карточки (пипсы)",
        icon="fa-calculator",
    )
    appbuilder.add_view(
        ContentCardIssueScheduleModelView,
        "Выдача карточек по расписанию",
        icon="fa-clock-o",
    )
    appbuilder.add_view(
        UsersWithCardsView,
        "Пользователи с карточками",
        icon="fa-table",
    )
    appbuilder.add_view(
        UsersWithPipCountCardsView,
        "Пользователи с карточками (пипсы)",
        icon="fa-table",
    )
    appbuilder.add_link(
        "Кабинет карточек",
        href="/admin/cards-cabinet",
        icon="fa-th-large",
    )
    appbuilder.add_link(
        "Кабинет пипсов",
        href="/admin/pip-count-cabinet",
        icon="fa-th",
    )


def create_app_for_flask_cli():
    """Helper factory for Flask CLI: returns only the Flask app object."""
    app, _ = create_app()
    return app


if __name__ == "__main__":
    app, appbuilder = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
