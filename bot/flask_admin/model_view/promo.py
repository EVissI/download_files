from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from bot.db.models import Promocode, PromocodeServiceQuantity
from flask import redirect, url_for
from sqlalchemy.orm import joinedload

class PromocodeServiceQuantityInline(ModelView, CompactCRUDMixin):
    """Инлайн-вьюха для услуг — именно с CompactCRUDMixin для компактного CRUD на одной странице"""

    datamodel = SQLAInterface(PromocodeServiceQuantity)

    # Разрешаем все операции
    can_create = True
    can_edit = True
    can_delete = True
    can_show = False
    can_list = True

    # Колонки для отображения и формы
    list_columns = ["service_type", "quantity"]
    form_columns = ["service_type", "quantity"]

    column_labels = {
        "service_type": _("Тип услуги"),
        "quantity": _("Количество (пусто = ∞)"),
    }

    column_descriptions = {
        "quantity": _("Оставьте пустым для неограниченного количества"),
    }

    # Красивое отображение ∞
    column_formatters = {
        "quantity": lambda v, c, m, p: (
            "∞" if m.quantity is None or m.quantity <= 0 else str(m.quantity)
        ),
        
    }
    add_exclude_columns = ["created_at", "updated_at"]
    edit_exclude_columns = ["created_at", "updated_at"]
    page_size = 50
    show_columns = []


class PromocodeModelView(ModelView):
    datamodel = SQLAInterface(Promocode)

    list_columns = [
        "code",
        "is_active",
        "max_usage_display",
        "activate_count_display",
        "duration_days_display",
        "services_summary",
    ]

    add_columns = edit_columns = [
        "code",
        "is_active",
        "max_usage",           
        "duration_days",       
    ]

    show_columns = [
        "code",
        "is_active",
        "max_usage_display",
        "activate_count_display",
        "duration_days_display",
        "services_summary",
    ]

    search_columns = ["code"]

    column_labels = {
        "code": _("Код промокода"),
        "is_active": _("Активен"),
        "max_usage_display": _("Макс. использований"),
        "activate_count_display": _("Использовано раз"),
        "duration_days_display": _("Длительность (дней)"),
        "services_summary": _("Услуги"),
    }

    column_descriptions = {
        "max_usage": _("Пусто = неограничено"),
        "duration_days": _("Пусто = бессрочно"),
        "services_summary": _("Список услуг, на которые распространяется промокод"),
    }

    related_views = [PromocodeServiceQuantityInline]

    # Обязательно подгружаем services, чтобы property работал быстро и без N+1 запросов
    def get_query(self):
        return super().get_query().options(joinedload(Promocode.services))

    def get_count_query(self):
        return super().get_count_query().options(joinedload(Promocode.services))

    column_filters = ["is_active"]
    column_searchable_list = ["code"]
    column_filterable_list = ["is_active"]
    
    column_default_sort = ("id", True)

    list_title = _("Промокоды")
    add_title = edit_title = _("Редактировать промокод")
    show_title = _("Просмотр промокода")

    def pre_add(self, item):
        item.activate_count = 0

    def post_add(self, item):
        if item.activate_count is None:
            item.activate_count = 0
            self.datamodel.session.commit()
        self._last_added_id = item.id

    def post_add_redirect(self):
        if hasattr(self, "_last_added_id"):
            url = url_for(f"{self.endpoint}.edit", pk=self._last_added_id)
            delattr(self, "_last_added_id")
            return redirect(url)
        return super().post_add_redirect()