from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.views import CompactCRUDMixin as CompactMixin  # На всякий случай
from flask_babel import lazy_gettext as _

from bot.db.models import Promocode, PromocodeServiceQuantity


class PromocodeServiceQuantityInline(ModelView, CompactCRUDMixin):
    """Инлайн-вью для услуг промокода — позволяет создавать новые записи, а не привязывать существующие"""
    
    datamodel = SQLAInterface(PromocodeServiceQuantity)

    can_create = True
    can_edit = True
    can_delete = True
    can_view_details = False
    can_show = False

    list_columns = ["service_type", "quantity"]
    form_columns = ["service_type", "quantity"]  # Только эти поля в форме добавления/редактирования

    column_labels = {
        "service_type": _("Тип услуги"),
        "quantity": _("Количество (пусто или 0 = ∞)"),
    }

    column_descriptions = {
        "quantity": _("Оставьте пустым для неограниченного количества"),
    }

    # Отображение ∞ вместо None или 0
    column_formatters = {
        "quantity": lambda v, c, m, p: "∞" if m.quantity is None or m.quantity <= 0 else str(m.quantity),
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

    add_columns = edit_columns = [
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
        "max_usage": _("Максимальное количество активаций. Пусто = неограничено"),
        "activate_count": _("Сколько раз уже активирован"),
        "duration_days": _("На сколько дней даётся доступ. Пусто = бессрочно"),
    }

    # Ключевой момент: используем список с классом инлайн-вьюхи и CompactCRUDMixin
    inline_models = [PromocodeServiceQuantityInline]

    # Сводка услуг в списке промокодов
    column_formatters = {
        "services_summary": lambda v, c, m, n: ", ".join(str(s) for s in m.services) if m.services else "-",
        "max_usage": lambda v, c, m, n: "∞" if m.max_usage is None else m.max_usage,
        "duration_days": lambda v, c, m, n: "∞" if m.duration_days is None else m.duration_days,
    }

    column_default_sort = ("id", True)

    column_filters = ["is_active", "max_usage", "duration_days"]

    list_title = _("Промокоды")
    add_title = edit_title = _("Редактировать промокод")
    show_title = _("Просмотр промокода")