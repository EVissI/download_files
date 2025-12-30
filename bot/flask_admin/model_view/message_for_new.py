from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from bot.db.models import MessageForNew
from flask_babel import lazy_gettext as _


class MessageForNewModelView(ModelView):
    datamodel = SQLAInterface(MessageForNew)

    # Запрещаем создание новых записей
    can_create = False
    can_delete = False
    can_edit = True
    can_show = True
    can_list = True

    list_title = _("Сообщения для новых пользователей")
    show_title = _("Сообщение")
    edit_title = _("Редактировать сообщение")

    list_columns = [
        "id",
        "lang_code",
        "dispatch_day",
        "dispatch_time",
        "text",  
    ]

    edit_columns = [
        "text",
        "lang_code",
        "dispatch_day",
        "dispatch_time",
    ]

    show_columns = [
        "id",
        "lang_code",
        "dispatch_day",
        "dispatch_time",
        "text",
    ]

    search_columns = ["text", "lang_code", "dispatch_day"]

    label_columns = {
        "id": "ID",
        "text": "Текст сообщения",
        "text_preview": "Текст сообщения",
        "lang_code": "Язык",
        "dispatch_day": "День отправки",
        "dispatch_time": "Время отправки",
    }

    order_columns = ["dispatch_day", "dispatch_time", "lang_code"]