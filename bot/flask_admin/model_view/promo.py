from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_babel import lazy_gettext as _
from bot.db.models import Promocode, PromocodeServiceQuantity
from flask import redirect, url_for
from sqlalchemy.orm import joinedload

class PromocodeServiceQuantityInline(ModelView, CompactCRUDMixin):
    """Инлайн-вьюха для услуг — именно с CompactCRUDMixin для компактного CRUD на одной странице"""

    datamodel = SQLAInterface(PromocodeServiceQuantity)
    list_title = "Услуги"
    can_create = True
    can_edit = True
    can_delete = True
    can_show = False
    can_list = True

    list_columns = ["service_type", "quantity"]
    form_columns = ["service_type", "quantity"]

    label_columns = {'service_type':'Сервис',
                     'quantity':'Кол-во',}
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

    label_columns = {'code':'Название',
                     'is_active':'Активен?',
                     'max_usage_display':'Макс использований',
                     'activate_count_display':'Кол-во использований',
                     'duration_days_display':'Длительность',
                     'services_summary':'Услуги',}
    
    add_columns = edit_columns = [
        "code",
        "is_active",
        "max_usage",           
        "duration_days",       
    ]
    order_columns = ['code', 'is_active']
    show_columns = [
        "code",
        "is_active",
        "max_usage_display",
        "activate_count_display",
        "duration_days_display",
        "services_summary",
    ]

    search_columns = ["code"]


    related_views = [PromocodeServiceQuantityInline]

    def get_query(self):
        return super().get_query().options(joinedload(Promocode.services))

    def get_count_query(self):
        return super().get_count_query().options(joinedload(Promocode.services))


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