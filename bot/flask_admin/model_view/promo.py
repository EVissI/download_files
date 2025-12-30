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
    quantity = IntegerField("Количество", default=0, validators=[NumberRange(min=0)])


class PromocodeServiceQuantityAdmin(ModelView):
    datamodel = SQLAInterface(PromocodeServiceQuantity)
    form = PromocodeServiceForm
    form_columns = ["service_type", "quantity"]
    list_columns = ["service_type", "quantity"]
    add_columns = edit_columns = ["service_type", "quantity"]


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
    ]

    exclude_columns = ["services"]  # Исключаем поле services из форм

    # Используем related_views для управления услугами в отдельных вкладках
    related_views = [PromocodeServiceQuantityAdmin]

    label_columns = {
        "code": "Код промокода",
        "is_active": "Активен",
        "max_usage": "Макс. использований",
        "activate_count": "Уже активировано",
        "duration_days": "Срок действия (дней)",
        "services": "Услуги",
        "services_summary": "Услуги",
    }

    description_columns = {
        "services": "Добавьте услуги: выберите тип и укажите количество (0 = неограниченно)",
    }

    def services_summary(self, item):
        if not item.services:
            return "Нет услуг"
        services_list = []
        for service in item.services:
            qty = service.quantity if service.quantity > 0 else "∞"
            services_list.append(f"{service.service_type.value}: {qty}")
        return ", ".join(services_list)

    services_summary.label = "Услуги"

    page_size = 20
