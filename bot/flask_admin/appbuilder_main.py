from flask import Flask
from flask_appbuilder import AppBuilder, IndexView, ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
import logging

logger = logging.getLogger(__name__)

from bot.config import settings
from bot.db.models import (
    User,
    UserGroup,
    UserInGroup,
    Promocode,
    PromocodeServiceQuantity,
    UserPromocode,
    UserPromocodeService,
    MessageForNew,
    AnalizePayment,
    AnalizePaymentServiceQuantity,
    UserAnalizePayment,
    UserAnalizePaymentService,
)

# === СИНХРОННАЯ БД ДЛЯ FLASK-APPBUILDER ===
db = SQLAlchemy()


class CustomIndexView(IndexView):
    """Кастомная главная страница"""

    title = "Dashboard"


def create_app():
    """Создание Flask-AppBuilder приложения с аутентификацией"""

    app = Flask(__name__)

    # === КОНФИГУРАЦИЯ ===
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DB_URL.replace(
        "+asyncpg", ""
    )  
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DB_URL.replace(
        "db", "localhost"
    )  
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["WTF_CSRF_ENABLED"] = True

    # === FLASK-APPBUILDER КОНФИГ ===
    app.config["FLASK_APP_BUILDER"] = {
        "THEME": "bootstrap4.html",
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

    # === ПОЛЬЗОВАТЕЛИ И ГРУППЫ ===

    class UserAdmin(ModelView):
        datamodel = SQLAInterface(User)
        list_columns = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "lang_code",
        ]
        search_columns = ["username", "first_name", "last_name", "email"]
        page_size = 20
        show_columns = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "lang_code",
        ]
        add_columns = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "lang_code",
        ]
        edit_columns = [
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "lang_code",
        ]

    class UserGroupAdmin(ModelView):
        datamodel = SQLAInterface(UserGroup)
        list_columns = ["id", "name"]
        search_columns = ["name"]
        page_size = 20

    class UserInGroupAdmin(ModelView):
        datamodel = SQLAInterface(UserInGroup)
        list_columns = ["id", "user_id", "group_id"]
        page_size = 20

    # === ПРОМОКОДЫ ===

    class PromocodeAdmin(ModelView):
        datamodel = SQLAInterface(Promocode)
        list_columns = [
            "id",
            "code",
            "is_active",
            "max_usage",
            "activate_count",
            "duration_days",
        ]
        search_columns = ["code"]
        page_size = 20
        show_columns = list_columns

    class PromocodeServiceQuantityAdmin(ModelView):
        datamodel = SQLAInterface(PromocodeServiceQuantity)
        list_columns = ["id", "promocode_id", "service_type", "quantity"]
        page_size = 20

    class UserPromocodeAdmin(ModelView):
        datamodel = SQLAInterface(UserPromocode)
        list_columns = ["id", "user_id", "promocode_id", "is_active"]
        page_size = 20

    class UserPromocodeServiceAdmin(ModelView):
        datamodel = SQLAInterface(UserPromocodeService)
        list_columns = ["id", "user_promocode_id", "service_type", "remaining_quantity"]
        page_size = 20

    # === СООБЩЕНИЯ ДЛЯ НОВЫХ ===

    class MessageForNewAdmin(ModelView):
        datamodel = SQLAInterface(MessageForNew)
        list_columns = ["id", "text", "lang_code", "dispatch_day", "dispatch_time"]
        search_columns = ["text"]
        page_size = 20

    # === ПЛАТЕЖИ АНАЛИЗОВ ===

    class AnalizePaymentAdmin(ModelView):
        datamodel = SQLAInterface(AnalizePayment)
        list_columns = ["id", "name", "price", "duration_days", "is_active"]
        search_columns = ["name"]
        page_size = 20

    class AnalizePaymentServiceQuantityAdmin(ModelView):
        datamodel = SQLAInterface(AnalizePaymentServiceQuantity)
        list_columns = ["id", "analize_payment_id", "service_type", "quantity"]
        page_size = 20

    class UserAnalizePaymentAdmin(ModelView):
        datamodel = SQLAInterface(UserAnalizePayment)
        list_columns = [
            "id",
            "user_id",
            "analize_payment_id",
            "tranzaction_id",
            "is_active",
        ]
        search_columns = ["tranzaction_id"]
        page_size = 20

    class UserAnalizePaymentServiceAdmin(ModelView):
        datamodel = SQLAInterface(UserAnalizePaymentService)
        list_columns = [
            "id",
            "user_analize_payment_id",
            "service_type",
            "remaining_quantity",
        ]
        page_size = 20

    # === ДОБАВЛЕНИЕ В АДМИНКУ ===
    appbuilder.add_view(
        UserAdmin, "Пользователи", icon="fa-users", category="Пользователи"
    )
    appbuilder.add_view(
        UserGroupAdmin, "Группы", icon="fa-sitemap", category="Пользователи"
    )
    appbuilder.add_view(
        UserInGroupAdmin,
        "Пользователи в группах",
        icon="fa-link",
        category="Пользователи",
    )

    appbuilder.add_view(
        PromocodeAdmin, "Промокоды", icon="fa-ticket", category="Промокоды"
    )
    appbuilder.add_view(
        PromocodeServiceQuantityAdmin,
        "Услуги промокодов",
        icon="fa-cube",
        category="Промокоды",
    )
    appbuilder.add_view(
        UserPromocodeAdmin,
        "Промокоды пользователей",
        icon="fa-user-tie",
        category="Промокоды",
    )
    appbuilder.add_view(
        UserPromocodeServiceAdmin,
        "Услуги пользователей",
        icon="fa-cog",
        category="Промокоды",
    )

    appbuilder.add_view(
        MessageForNewAdmin,
        "Сообщения для новых",
        icon="fa-envelope",
        category="Рассылки",
    )

    appbuilder.add_view(
        AnalizePaymentAdmin,
        "Платежи анализов",
        icon="fa-credit-card",
        category="Анализы",
    )
    appbuilder.add_view(
        AnalizePaymentServiceQuantityAdmin,
        "Услуги платежей",
        icon="fa-tasks",
        category="Анализы",
    )
    appbuilder.add_view(
        UserAnalizePaymentAdmin,
        "Платежи пользователей",
        icon="fa-money",
        category="Анализы",
    )
    appbuilder.add_view(
        UserAnalizePaymentServiceAdmin,
        "Услуги платежей пользователей",
        icon="fa-list",
        category="Анализы",
    )


def create_app_for_flask_cli():
    """Helper factory for Flask CLI: returns only the Flask app object."""
    app, _ = create_app()
    return app


if __name__ == "__main__":
    app, appbuilder = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
