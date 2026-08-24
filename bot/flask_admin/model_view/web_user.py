from flask import flash, request
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from wtforms import PasswordField
from wtforms.validators import DataRequired, Length, Optional

from bot.common.utils.password import hash_password
from bot.db.models import WebUser

try:
    from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget
except ImportError:  # pragma: no cover
    BS3PasswordFieldWidget = None


def _password_field(label: str, required: bool) -> PasswordField:
    validators = [Length(min=6, max=128)]
    validators.insert(0, DataRequired() if required else Optional())
    kwargs = {"validators": validators}
    if BS3PasswordFieldWidget is not None:
        kwargs["widget"] = BS3PasswordFieldWidget()
    return PasswordField(label, **kwargs)


class WebUserModelView(ModelView):
    datamodel = SQLAInterface(WebUser)

    list_title = "Веб-пользователи"
    show_title = "Веб-пользователь"
    add_title = "Создать веб-пользователя"
    edit_title = "Изменить веб-пользователя"

    list_columns = ["id", "login", "is_admin", "password_masked"]
    show_columns = ["id", "login", "is_admin", "password_masked"]
    add_columns = ["login", "is_admin"]
    edit_columns = ["login", "is_admin"]
    search_columns = ["login"]
    exclude_columns = ["password_hash", "uploads"]

    label_columns = {
        "id": "ID",
        "login": "Логин",
        "is_admin": "Админ",
        "password_masked": "Пароль",
    }
    description_columns = {
        "is_admin": "Флаг хранится в БД и не принимается из клиентских запросов веб-ошибок.",
        "password_masked": "Хеш не показывается. Новый пароль задаётся только в форме создания/редактирования.",
    }

    add_form_extra_fields = {
        "password": _password_field("Пароль", required=True),
    }
    edit_form_extra_fields = {
        "password": _password_field("Новый пароль (оставьте пустым, чтобы не менять)", required=False),
    }

    def pre_add(self, item: WebUser) -> None:
        item.login = (item.login or request.form.get("login") or "").strip()
        if not item.login:
            flash("Логин обязателен", "danger")
            raise ValueError("login required")
        existing = (
            self.datamodel.session.query(WebUser)
            .filter(WebUser.login == item.login)
            .first()
        )
        if existing:
            flash("Такой логин уже занят", "danger")
            raise ValueError("duplicate login")
        raw = (request.form.get("password") or "").strip()
        if len(raw) < 6:
            flash("Пароль должен быть не короче 6 символов", "danger")
            raise ValueError("password too short")
        item.password_hash = hash_password(raw)
        item.is_admin = bool(item.is_admin)

    def pre_update(self, item: WebUser) -> None:
        item.login = (item.login or request.form.get("login") or "").strip()
        if not item.login:
            flash("Логин обязателен", "danger")
            raise ValueError("login required")
        existing = (
            self.datamodel.session.query(WebUser)
            .filter(WebUser.login == item.login, WebUser.id != item.id)
            .first()
        )
        if existing:
            flash("Такой логин уже занят", "danger")
            raise ValueError("duplicate login")
        raw = (request.form.get("password") or "").strip()
        if raw:
            if len(raw) < 6:
                flash("Пароль должен быть не короче 6 символов", "danger")
                raise ValueError("password too short")
            item.password_hash = hash_password(raw)
        item.is_admin = bool(item.is_admin)
