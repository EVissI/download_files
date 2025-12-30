from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView
from flask_appbuilder.forms import DynamicForm
from wtforms import SelectField, IntegerField
from wtforms.validators import DataRequired, NumberRange

from bot.db.models import Promocode, PromocodeServiceQuantity, ServiceType


class PromocodeServiceForm(DynamicForm):
    service_type = SelectField(
        "Тип услуги",
        choices=[(st.value, st.value) for st in ServiceType],
        validators=[DataRequired()],
    )
    quantity = IntegerField(
        "Количество",
        validators=[
            NumberRange(min=0, message="Количество должно быть неотрицательным")
        ],
    )


class PromocodeAdmin(ModelView):
    datamodel = SQLAInterface(Promocode)

    list_columns = [
        "id",
        "code",
        "is_active",
        "max_usage",
        "activate_count",
        "duration_days",
        "services_summary",
    ]
    show_columns = list_columns + ["services"]
    search_columns = ["code"]

    add_columns = edit_columns = [
        "code",
        "is_active",
        "max_usage",
        "activate_count",
        "duration_days",
        "services",  # инлайн-таблица
    ]

    # Настройка inline-формы для услуг
    inline_models = [
        {
            "model": PromocodeServiceQuantity,
            "form": PromocodeServiceForm,
            "form_label": "Услуги промокода",
            "form_columns": ["service_type", "quantity"],
            "form_label_columns": {
                "service_type": "Тип услуги",
                "quantity": "Количество",
            },
            "form_widget_args": {
                "service_type": {
                    "description": "Выберите тип услуги, которую предоставляет промокод"
                },
                "quantity": {
                    "description": "Укажите количество услуг (оставьте 0 для неограниченного количества)"
                },
            },
        }
    ]

    label_columns = {
        "code": "Код промокода",
        "is_active": "Активен",
        "max_usage": "Макс. использований",
        "activate_count": "Уже активировано",
        "duration_days": "Срок действия (дней)",
        "services": "Услуги",
        "services_summary": "Услуги",
    }

    # Метод для отображения сводки по услугам в списке
    def services_summary(self, item):
        if not item.services:
            return "Нет услуг"

        services_list = []
        for service in item.services:
            if service.quantity is not None and service.quantity > 0:
                services_list.append(
                    f"{service.service_type.value}: {service.quantity}"
                )
            else:
                services_list.append(f"{service.service_type.value}: ∞")

        return ", ".join(services_list)

    services_summary.label = "Услуги"

    description_columns = {
        "max_usage": "Оставьте пустым для неограниченного количества использований",
        "activate_count": "Автоматически увеличивается при активации (можно задать вручную)",
        "duration_days": "Оставьте пустым, если промокод бессрочный",
        "services": "Услуги, предоставляемые по промокоду",
    }

    # Настройка отображения inline-формы в режиме просмотра
    show_inline_models = [
        {
            "model": PromocodeServiceQuantity,
            "form": PromocodeServiceForm,
            "form_label": "Услуги промокода",
            "form_columns": ["service_type", "quantity"],
            "form_label_columns": {
                "service_type": "Тип услуги",
                "quantity": "Количество",
            },
        }
    ]

    page_size = 20
