from flask_appbuilder import ModelView, CompactCRUDMixin
from flask_appbuilder.models.sqla.interface import SQLAInterface
from wtforms import BooleanField, IntegerField
from wtforms.validators import Optional, NumberRange
from bot.db.models import (
    Promocode,
    PromocodeServiceQuantity,
    PromocodeType,
    ServiceType,
)
from flask import flash, redirect, request, url_for
from loguru import logger
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
    add_template = "promocode_add.html"
    edit_template = "promocode_edit.html"

    list_columns = [
        "code",
        "is_active",
        "max_usage_display",
        "activate_count_display",
        "duration_days_display",
        "promocode_type",
        "cards_issue_quantity",
        "services_summary",
    ]
    title = "Промокод"
    label_columns = {'code':'Название',
                     'is_active':'Активен?',
                     'max_usage_display':'Макс использований',
                     'activate_count_display':'Кол-во использований',
                     'duration_days_display':'Длительность',
                     'promocode_type':'Тип промокода',
                     'cards_issue_quantity':'Выдавать карточек',
                     'max_usage':'Макс использований',
                     'activate_count':'Кол-во использований',
                     'duration_days':'Длительность',
                     'content_cards':'Карточки',
                     'services_summary':'Услуги',
                     'autofill_services':'Автозаполнение',
                     'autofill_quantity':'Кол-во для всех сервисов',}
    
    edit_columns = [
        "code",
        "is_active",
        "promocode_type",
        "max_usage",           
        "duration_days",
        "cards_issue_quantity",
    ]
    add_columns = [
        "code",
        "is_active",
        "promocode_type",
        "max_usage",
        "duration_days",
        "cards_issue_quantity",
        "autofill_services",
        "autofill_quantity",
    ]
    order_columns = ['code', 'is_active']
    show_columns = [
        "code",
        "is_active",
        "max_usage_display",
        "activate_count_display",
        "duration_days_display",
        "promocode_type",
        "cards_issue_quantity",
        "services_summary",
    ]

    search_columns = ["code"]

    edit_form_extra_fields = {
        'is_active': BooleanField(
            label='Активен?',
            default=True,          
            render_kw={'required': False}  
        )
    }
    add_form_extra_fields = {
        'is_active': BooleanField(
            label='Активен?',
            default=True,
            render_kw={'required': False},
        ),
        'autofill_services': BooleanField(
            label='Автозаполнение',
            default=False,
            false_values=(False, "false", "0", ""),
            render_kw={'required': False},
        ),
        'autofill_quantity': IntegerField(
            label='Кол-во для всех сервисов',
            default=3000,
            validators=[Optional(), NumberRange(min=0, max=10_000_000)],
            render_kw={'required': False, 'min': 0},
        ),
    }
    related_views = [PromocodeServiceQuantityInline]

    def get_query(self):
        return super().get_query().options(
            joinedload(Promocode.services),
        )

    def get_count_query(self):
        return super().get_count_query().options(joinedload(Promocode.services))


    def _normalize_limits(self, item):
        """Преобразуем 0 в None для полей max_usage и duration_days."""
        if item.max_usage == 0:
            item.max_usage = None
        if item.duration_days == 0:
            item.duration_days = None
        if item.promocode_type == PromocodeType.CARDS:
            # Карточечные промокоды не должны истекать по времени.
            item.duration_days = None
        if item.promocode_type == PromocodeType.REGULAR:
            item.cards_issue_quantity = None
        elif not item.cards_issue_quantity or item.cards_issue_quantity <= 0:
            item.cards_issue_quantity = 1

    def pre_add(self, item):
        self._normalize_limits(item)
        item.activate_count = 0
        # Поля только формы — не атрибуты модели.
        for attr in ("autofill_services", "autofill_quantity"):
            if hasattr(item, attr):
                try:
                    delattr(item, attr)
                except Exception:
                    pass

    def pre_update(self, item):
        self._normalize_limits(item)

    def _parse_autofill_quantity(self) -> int | None:
        """None — автозаполнение выключено; иначе quantity (>=0)."""
        raw_flag = request.form.get("autofill_services")
        # Checkbox: present when checked (often "y" / "on" / "true")
        if raw_flag is None:
            return None
        flag = str(raw_flag).strip().lower()
        if flag in ("", "0", "false", "off", "no"):
            return None

        raw_qty = (request.form.get("autofill_quantity") or "3000").strip()
        try:
            qty = int(raw_qty)
        except (TypeError, ValueError):
            qty = 3000
        if qty < 0:
            qty = 0
        return qty

    def _autofill_all_services(self, item: Promocode, quantity: int) -> int:
        """Создаёт PromocodeServiceQuantity для каждого ServiceType. 0 → None (∞)."""
        session = self.datamodel.session
        store_qty = quantity if quantity > 0 else None
        created = 0
        for service_type in ServiceType:
            session.add(
                PromocodeServiceQuantity(
                    promocode_id=item.id,
                    service_type=service_type,
                    quantity=store_qty,
                )
            )
            created += 1
        session.commit()
        return created

    def post_add(self, item):
        if item.activate_count is None:
            item.activate_count = 0
            self.datamodel.session.commit()

        qty = self._parse_autofill_quantity()
        if qty is not None:
            try:
                n = self._autofill_all_services(item, qty)
                flash(
                    f"Автозаполнение: добавлено сервисов — {n}, количество — "
                    f"{'∞' if qty == 0 else qty}.",
                    "info",
                )
            except Exception as e:
                self.datamodel.session.rollback()
                logger.exception("Promocode autofill failed for id={}: {}", item.id, e)
                flash(f"Промокод создан, но автозаполнение сервисов не удалось: {e}", "warning")

        self._last_added_id = item.id

    def post_add_redirect(self):
        if hasattr(self, "_last_added_id"):
            url = url_for(f"{self.endpoint}.edit", pk=self._last_added_id)
            delattr(self, "_last_added_id")
            return redirect(url)
        return super().post_add_redirect()
