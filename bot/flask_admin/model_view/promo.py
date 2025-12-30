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
        "max_usage",
        "activate_count",
        "duration_days",
        "services_summary",
    ]

    add_columns = edit_columns = show_columns = [
        "code",
        "is_active",
        "max_usage",
        "duration_days",
    ]

    search_columns = ["code"]

    column_labels = {
        "code": _("Код промокода"),
        "is_active": _("Активен"),
        "max_usage": _("Макс. использований"),
        "activate_count": _("Использовано раз"),
        "duration_days": _("Длительность (дней)"),
        "services_summary": _("Услуги"),
    }

    column_descriptions = {
        "max_usage": _("Пусто = неограничено"),
        "duration_days": _("Пусто = бессрочно"),
    }

    related_views = [PromocodeServiceQuantityInline]

    # Подгружаем связанные услуги
    def get_query(self):
        return super().get_query().options(joinedload(Promocode.services))

    def get_count_query(self):
        return super().get_count_query().options(joinedload(Promocode.services))

    def _list_services_summary(self, model):
            """Надёжная сводка услуг через прямой запрос"""
            services = (
                self.datamodel.session.query(PromocodeServiceQuantity)
                .filter_by(promocode_id=model.id)
                .order_by(PromocodeServiceQuantity.id)  # для стабильного порядка
                .all()
            )
            
            if not services:
                return "—"
            
            return ", ".join(str(s) for s in services)

    column_formatters = {
        "services_summary": "_list_services_summary",
        "max_usage": lambda v, c, m, n: "∞" if m.max_usage is None else str(m.max_usage),
        "duration_days": lambda v, c, m, n: "∞" if m.duration_days is None else str(m.duration_days),
        "activate_count": lambda v, c, m, n: str(m.activate_count or 0),
    }
    
    column_filters = ["is_active"]
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