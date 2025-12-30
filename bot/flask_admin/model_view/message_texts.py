from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.fieldwidgets import BS3TextAreaFieldWidget
from wtforms import TextAreaField
from wtforms.validators import DataRequired, Length
from flask_babel import lazy_gettext as _

from bot.db.models import MessagesTexts


class MessagesTextsModelView(ModelView):
    datamodel = SQLAInterface(MessagesTexts)

    # Основные настройки
    can_create = True
    can_edit = True
    can_delete = True
    can_show = True
    can_list = True

    page_size = 50

    list_title = _("Тексты сообщений")
    add_title = _("Добавить текст")
    edit_title = _("Редактировать текст")
    show_title = _("Просмотр текста")

    # Колонки в списке
    list_columns = [
        "code",
        "text_ru",
        "text_en",
    ]

    # Поля в форме добавления/редактирования
    add_columns = edit_columns = [
        "code",
        "text_ru",
        "text_en",
    ]

    # Поля при просмотре одной записи
    show_columns = [
        "code",
        "text_ru",
        "text_en",
    ]

    # Поиск по коду и текстам
    search_columns = ["code", "text_ru", "text_en"]

    # Метки
    label_columns = {
        "code": _("Код"),
        "text_ru": _("Текст (RU)"),
        "text_en": _("Текст (EN)"),
    }

    # Подсказки в форме
    description_columns = {
        "code": _("Уникальный код для обращения к тексту в коде бота (например: welcome_message, gift_notification)"),
        "text_ru": _("Текст на русском. Поддерживается HTML-разметка. До 1000 символов."),
        "text_en": _("Текст на английском. Поддерживается HTML-разметка. До 1000 символов."),
    }

    # Сортировка по умолчанию
    order_columns = ["code"]
