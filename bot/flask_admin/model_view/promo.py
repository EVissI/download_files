
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import  ModelView
from flask_appbuilder.fieldwidgets import BS3TextFieldWidget
from flask_appbuilder.fields import AJAXSelectField

from bot.db.models import Promocode, PromocodeServiceQuantity


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

    # Основные поля формы
    form_columns = [
        "code",
        "is_active",
        "max_usage",
        "activate_count",
        "duration_days",
        "service_entries",  # наше кастомное поле
    ]

    label_columns = {
        "code": "Код промокода",
        "is_active": "Активен",
        "max_usage": "Макс. использований (пусто = без лимита)",
        "activate_count": "Уже активировано",
        "duration_days": "Срок действия в днях (пусто = бессрочный)",
        "service_entries": "Услуги в промокоде",
    }

    description_columns = {
        "max_usage": "Оставьте пустым для неограниченного количества использований",
        "activate_count": "Считается автоматически, но можно задать вручную",
        "duration_days": "Оставьте пустым, если промокод бессрочный",
    }

    # Кастомное поле для динамического добавления услуг
    form_extra_fields = {
        "service_entries": AJAXSelectField(
            label="Услуги",
            description="Добавьте нужные типы услуг и их количество",
            widget=BS3TextFieldWidget(),  # будет заменён на кастомный JS-виджет
            # Это поле будет обработано вручную через form_override
        )
    }

    # Переопределяем форму, чтобы использовать Multiple Related Services
    # Flask-AppBuilder поддерживает множественные связанные записи через form_add_related / form_edit_related
    # Но проще и красивее — использовать встроенную функцию Multiple Related
    form_related_models = {
        "services": {
            "model": PromocodeServiceQuantity,
            "related_field": "promocode",
            "list_columns": ["service_type", "quantity"],
            "form_columns": ["service_type", "quantity"],
            "label_columns": {
                "service_type": "Тип услуги",
                "quantity": "Количество",
            },
            "can_add": True,
            "can_delete": True,
            "can_edit": True,
            "add_title": "Добавить услугу",
            "edit_title": "Редактировать услугу",
        }
    }

    # Включаем поддержку множественных связанных моделей
    show_related = True
    edit_related = True
    add_related = True