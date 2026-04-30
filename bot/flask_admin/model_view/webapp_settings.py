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

    list_columns = ["id", "webapp_fullscreen_enabled"]
    show_columns = ["id", "webapp_fullscreen_enabled"]
    edit_columns = ["webapp_fullscreen_enabled"]

    form_overrides = {
        "webapp_fullscreen_enabled": SelectField,
    }
    form_args = {
        "webapp_fullscreen_enabled": {
            "label": _("Разрешать полноэкранный режим"),
            "choices": [(True, _("Включено")), (False, _("Выключено"))],
            "coerce": lambda x: str(x).strip().lower() in ("1", "true", "on", "yes"),
        }
    }

    label_columns = {
        "id": _("ID"),
        "webapp_fullscreen_enabled": _("Разрешать полноэкранный режим"),
        "created_at": _("Создано"),
        "updated_at": _("Обновлено"),
    }

    base_order = ("id", "asc")

    def post_update(self, item):
        flash(_("Настройка WebApp сохранена"), "success")
