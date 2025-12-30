from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView
from wtforms import SelectField

from bot.db.models import Promocode, PromocodeServiceQuantity, ServiceType


class PromocodeServiceQuantityInline(ModelView):
    """Инлайн-модель для количества услуг в промокоде"""

    datamodel = SQLAInterface(PromocodeServiceQuantity)

    list_columns = ["service_type", "quantity"]
    form_columns = ["service_type", "quantity"]
    label_columns = {
        "service_type": "Тип услуги",
        "quantity": "Количество",
    }

    form_overrides = {"service_type": SelectField}

    form_args = {"service_type": {"choices": [(e.value, e.value) for e in ServiceType]}}


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

    label_columns = {
        "code": "Код промокода",
        "is_active": "Активен",
        "max_usage": "Макс. использований",
        "activate_count": "Уже активировано",
        "duration_days": "Срок действия (дней)",
        "services": "Услуги",
    }

    description_columns = {
        "max_usage": "Оставьте пустым для неограниченного количества использований",
        "activate_count": "Автоматически увеличивается при активации (можно задать вручную)",
        "duration_days": "Оставьте пустым, если промокод бессрочный",
    }

    inline_models = [
        (PromocodeServiceQuantityInline, {"form_columns": ["service_type", "quantity"]})
    ]

    page_size = 20
