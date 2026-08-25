from datetime import timezone
from zoneinfo import ZoneInfo

from flask import flash, request
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from wtforms import BooleanField, DateTimeLocalField, PasswordField
from wtforms.validators import DataRequired, Length, Optional

from bot.common.utils.password import store_password
from bot.db.models import WebUser

try:
    from flask_appbuilder.fieldwidgets import BS3PasswordFieldWidget
except ImportError:  # pragma: no cover
    BS3PasswordFieldWidget = None

MSK = ZoneInfo("Europe/Moscow")


def _password_field(label: str, required: bool) -> PasswordField:
    validators = [Length(min=6, max=128)]
    validators.insert(0, DataRequired() if required else Optional())
    kwargs = {"validators": validators}
    if BS3PasswordFieldWidget is not None:
        kwargs["widget"] = BS3PasswordFieldWidget()
    return PasswordField(label, **kwargs)


def _unlimited_checked() -> bool:
    return request.form.get("unlimited") in ("y", "on", "1", "true", "True")


class WebUserModelView(ModelView):
    datamodel = SQLAInterface(WebUser)

    list_title = "Веб-пользователи"
    show_title = "Веб-пользователь"
    add_title = "Создать веб-пользователя"
    edit_title = "Изменить веб-пользователя"

    list_columns = [
        "id",
        "login",
        "is_admin",
        "account_status",
        "expires_at_display",
        "password_masked",
    ]
    show_columns = [
        "id",
        "login",
        "is_admin",
        "account_status",
        "expires_at_display",
        "password_display",
    ]
    add_columns = ["login", "password", "is_admin", "unlimited", "expires_at"]
    edit_columns = ["login", "password", "is_admin", "unlimited", "expires_at"]
    search_columns = ["login"]
    exclude_columns = ["password_hash", "password_encrypted", "uploads"]

    label_columns = {
        "id": "ID",
        "login": "Логин",
        "password": "Пароль",
        "is_admin": "Админ",
        "unlimited": "Бессрочный",
        "expires_at": "Активен до",
        "expires_at_display": "Активен до",
        "account_status": "Статус",
        "password_masked": "Пароль",
        "password_display": "Пароль",
    }
    description_columns = {
        "is_admin": "Флаг хранится в БД и не принимается из клиентских запросов веб-ошибок.",
        "password": "Не короче 6 символов. При редактировании оставьте пустым, чтобы не менять.",
        "password_masked": "В списке пароль скрыт. Откройте карточку пользователя, чтобы увидеть исходный пароль.",
        "password_display": "Расшифрованная копия. Для входа используется отдельный хеш.",
        "unlimited": "Если отмечено, срок не ограничен и вход всегда разрешён.",
        "expires_at": "Московское время. После этой даты войти нельзя. Не нужно, если аккаунт бессрочный.",
    }

    add_form_extra_fields = {
        "password": _password_field("Пароль", required=True),
        "unlimited": BooleanField("Бессрочный", default=False),
        "expires_at": DateTimeLocalField(
            "Активен до",
            validators=[Optional()],
            format="%Y-%m-%dT%H:%M",
        ),
    }
    edit_form_extra_fields = {
        "password": _password_field("Новый пароль (оставьте пустым, чтобы не менять)", required=False),
        "unlimited": BooleanField("Бессрочный", default=False),
        "expires_at": DateTimeLocalField(
            "Активен до",
            validators=[Optional()],
            format="%Y-%m-%dT%H:%M",
        ),
    }

    @staticmethod
    def _raw_password(item: WebUser) -> str:
        raw = getattr(item, "password", None)
        if not isinstance(raw, str) or not raw.strip():
            raw = request.form.get("password")
        return (raw or "").strip()

    @staticmethod
    def _drop_transient_password(item: WebUser) -> None:
        for name in ("password", "unlimited"):
            if hasattr(item, name):
                try:
                    delattr(item, name)
                except Exception:
                    pass

    def _apply_expiry(self, item: WebUser) -> None:
        if _unlimited_checked():
            item.expires_at = None
            return
        expires_at = item.expires_at
        if expires_at is None:
            flash("Укажите срок действия или отметьте «Бессрочный»", "danger")
            raise ValueError("expires_at required")
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=MSK)
        item.expires_at = expires_at.astimezone(timezone.utc)

    def prefill_form(self, form, pk):
        item = self.datamodel.get(pk)
        if item is None:
            return
        if getattr(form, "unlimited", None) is not None:
            form.unlimited.data = item.expires_at is None
        if item.expires_at is not None and getattr(form, "expires_at", None) is not None:
            local = item.expires_at
            if local.tzinfo is None:
                local = local.replace(tzinfo=timezone.utc)
            form.expires_at.data = local.astimezone(MSK).replace(tzinfo=None)

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
        raw = self._raw_password(item)
        if len(raw) < 6:
            flash("Пароль должен быть не короче 6 символов", "danger")
            raise ValueError("password too short")
        item.password_hash, item.password_encrypted = store_password(raw)
        item.is_admin = bool(item.is_admin)
        self._apply_expiry(item)
        self._drop_transient_password(item)

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
        raw = self._raw_password(item)
        if raw:
            if len(raw) < 6:
                flash("Пароль должен быть не короче 6 символов", "danger")
                raise ValueError("password too short")
            item.password_hash, item.password_encrypted = store_password(raw)
        item.is_admin = bool(item.is_admin)
        self._apply_expiry(item)
        self._drop_transient_password(item)
