from flask import flash
from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from wtforms import SelectField

from bot.db.models import WebAppSetting


class WebAppSettingsModelView(ModelView):
    datamodel = SQLAInterface(WebAppSetting)

    base_permissions = ["can_list", "can_show", "can_edit"]

    can_list = True
    can_show = True
    can_edit = True
    can_create = False
    can_delete = False

    list_title = _("Настройки WebApp")
    edit_title = _("Редактировать настройки WebApp")
    show_title = _("Просмотр настроек WebApp")

    list_columns = [
        "id",
        "webapp_fullscreen_hints_enabled",
        "webapp_fullscreen_pokaz_enabled",
        "webapp_fullscreen_cards_cabinet_enabled",
        "webapp_fullscreen_content_card_view_enabled",
        "webapp_fullscreen_admin_login_enabled",
        "webapp_fullscreen_player_enabled",
    ]
    show_columns = list_columns
    edit_columns = list_columns[1:]

    edit_form_extra_fields = {
        "webapp_fullscreen_hints_enabled": SelectField(
            _("Ошибки: полноэкранный режим"),
            choices=[("true", _("Включено")), ("false", _("Выключено"))],
            coerce=lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        ),
        "webapp_fullscreen_pokaz_enabled": SelectField(
            _("Позиции: полноэкранный режим"),
            choices=[("true", _("Включено")), ("false", _("Выключено"))],
            coerce=lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        ),
        "webapp_fullscreen_cards_cabinet_enabled": SelectField(
            _("Кабинет карточек: полноэкранный режим"),
            choices=[("true", _("Включено")), ("false", _("Выключено"))],
            coerce=lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        ),
        "webapp_fullscreen_content_card_view_enabled": SelectField(
            _("Просмотр карточки: полноэкранный режим"),
            choices=[("true", _("Включено")), ("false", _("Выключено"))],
            coerce=lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        ),
        "webapp_fullscreen_admin_login_enabled": SelectField(
            _("Админка: полноэкранный режим"),
            choices=[("true", _("Включено")), ("false", _("Выключено"))],
            coerce=lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        ),
        "webapp_fullscreen_player_enabled": SelectField(
            _("Плеер: полноэкранный режим"),
            choices=[("true", _("Включено")), ("false", _("Выключено"))],
            coerce=lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        ),
    }

    label_columns = {
        "id": _("ID"),
        "webapp_fullscreen_hints_enabled": _("Hints Viewer"),
        "webapp_fullscreen_pokaz_enabled": _("Pokaz"),
        "webapp_fullscreen_cards_cabinet_enabled": _("Кабинет карточек"),
        "webapp_fullscreen_content_card_view_enabled": _("Просмотр карточки"),
        "webapp_fullscreen_admin_login_enabled": _("Admin Login"),
        "webapp_fullscreen_player_enabled": _("Плеер"),
        "created_at": _("Создано"),
        "updated_at": _("Обновлено"),
    }

    base_order = ("id", "asc")

    def post_update(self, item):
        flash(_("Настройка WebApp сохранена"), "success")
