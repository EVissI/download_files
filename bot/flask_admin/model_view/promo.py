from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _

from bot.db.models import Promocode, PromocodeServiceQuantity, ServiceType


class PromocodeServiceQuantityView(ModelView):
    """Модель-вью для инлайн-редактирования услуг в промокоде"""
    
    datamodel = SQLAInterface(PromocodeServiceQuantity)

    can_create = True
    can_edit = True
    can_delete = True

    list_columns = ["service_type", "quantity"]
    edit_columns = ["service_type", "quantity"]
    add_columns = ["service_type", "quantity"]

    column_labels = {
        "service_type": _("Тип услуги"),
        "quantity": _("Количество (None = ∞)"),
    }

    column_descriptions = {
        "quantity": _("Укажите количество использований. Оставьте пустым или None для неограниченного."),
    }

    # Кастомное отображение количества (с ∞)
    column_formatters = {
        "quantity": lambda view, context, model, name: "∞" if model.quantity is None else model.quantity,
    }


class PromocodeModelView(ModelView):
    datamodel = SQLAInterface(Promocode)

    list_columns = [
        "code",
        "is_active",
        "max_usage",
        "activate_count",
        "duration_days",
        "services_summary",
    ]

    show_columns = [
        "id",
        "code",
        "is_active",
        "max_usage",
        "activate_count",
        "duration_days",
        "services",
        "users",
    ]

    edit_columns = add_columns = [
        "code",
        "is_active",
        "max_usage",
        "activate_count",
        "duration_days",
        "services",
    ]

    search_columns = ["code"]

    column_labels = {
        "code": _("Код промокода"),
        "is_active": _("Активен"),
        "max_usage": _("Макс. использований"),
        "activate_count": _("Использовано раз"),
        "duration_days": _("Длительность (дней)"),
        "services": _("Услуги"),
        "users": _("Пользователи"),
    }

    column_descriptions = {
        "max_usage": _("Максимальное количество активаций. None = неограничено"),
        "activate_count": _("Сколько раз уже активирован"),
        "duration_days": _("На сколько дней даётся доступ после активации. None = бессрочно"),
    }

    # Инлайн-редактирование услуг
    inline_models = (PromocodeServiceQuantityView,)

    # Красивое отображение списка услуг в списке промокодов
    column_formatters = {
        "services_summary": lambda view, context, model, name: ", ".join(str(s) for s in model.services) if model.services else "-",
        "max_usage": lambda view, context, model, name: "∞" if model.max_usage is None else model.max_usage,
        "duration_days": lambda view, context, model, name: "∞" if model.duration_days is None else model.duration_days,
    }

    column_default_sort = ("id", True)

    # Фильтры
    column_filters = [
        "is_active",
        "max_usage",
        "duration_days",
    ]

    # Кастомный заголовок списка
    list_title = _("Промокоды")
    add_title = edit_title = _("Редактировать промокод")
    show_title = _("Просмотр промокода")