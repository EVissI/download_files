from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from bot.db.models import AnalizePayment, AnalizePaymentServiceQuantity
from flask import redirect, url_for
from sqlalchemy.orm import joinedload


class AnalizePaymentServiceQuantityInline(ModelView, CompactCRUDMixin):
    """Инлайн-вьюха для услуг в платежах — компактный CRUD на одной странице"""

    datamodel = SQLAInterface(AnalizePaymentServiceQuantity)

    list_title = "Услуги"
    can_create = True
    can_edit = True
    can_delete = True
    can_show = False
    can_list = True

    list_columns = ["service_type", "quantity"]
    form_columns = ["service_type", "quantity"]

    label_columns = {
        'service_type': 'Сервис',
        'quantity': 'Кол-во',
    }

    add_exclude_columns = edit_exclude_columns = ["created_at", "updated_at"]
    page_size = 50
    show_columns = []


class AnalizePaymentModelView(ModelView):
    datamodel = SQLAInterface(AnalizePayment)

    list_columns = [
        "name",
        "price",
        "is_active",
        "duration_days_display",
        "services_summary",
    ]

    title = "Пакеты"
    
    label_columns = {
        'name': 'Название',
        'price': 'Цена',
        'is_active': 'Активен?',
        'duration_days': 'Длительность',
        'duration_days_display': 'Длительность',
        'services_summary': 'Услуги',
    }

    add_columns = edit_columns = [
        "name",
        "price",
        "is_active",
        "duration_days",
    ]

    order_columns = ['name', 'price', 'is_active']
    
    show_columns = [
        "name",
        "price",
        "is_active",
        "duration_days_display",
        "services_summary",
    ]

    search_columns = ["name"]

    related_views = [AnalizePaymentServiceQuantityInline]

    # Предзагружаем связанные услуги для корректного отображения services_summary
    def get_query(self):
        return super().get_query().options(joinedload(AnalizePayment.services))

    def get_count_query(self):
        return super().get_count_query().options(joinedload(AnalizePayment.services))

    # Редирект на редактирование после создания (чтобы сразу добавить услуги)
    def post_add(self, item):
        self._last_added_id = item.id

    def post_add_redirect(self):
        if hasattr(self, "_last_added_id"):
            url = url_for(f"{self.endpoint}.edit", pk=self._last_added_id)
            delattr(self, "_last_added_id")
            return redirect(url)
        return super().post_add_redirect()