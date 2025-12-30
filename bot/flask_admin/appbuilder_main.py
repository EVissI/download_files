from flask import Flask
from flask_appbuilder import AppBuilder, IndexView, ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import declarative_base
import logging

from bot.flask_admin.model_view.promo import PromocodeModelView, PromocodeServiceQuantityInline

logger = logging.getLogger(__name__)

from bot.config import settings


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
    ).replace(
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
    
    appbuilder.add_view_no_menu(PromocodeServiceQuantityInline)
    appbuilder.add_view(
        PromocodeModelView,
        "Промокоды",
        icon="fa-cube",
        category="Управление",
        category_icon="fa-cube"
    )

def create_app_for_flask_cli():
    """Helper factory for Flask CLI: returns only the Flask app object."""
    app, _ = create_app()
    return app


if __name__ == "__main__":
    app, appbuilder = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
