from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from bot.db.models import User, UserPromocode, UserAnalizePayment, Promocode
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload


class CustomUserSQLAInterface(SQLAInterface):
    """Кастомный SQLAInterface для обработки сортировки по активным промокодам"""
    
    def apply_order_by(self, query, order_column, order_direction, **kwargs):
        """Переопределяем метод для обработки сортировки по кастомным полям"""
        # Если сортировка по active_promocodes, используем подзапрос
        if order_column == 'active_promocodes':
            active_promocodes_count = (
                select(func.count(UserPromocode.id))
                .where(
                    UserPromocode.user_id == User.id,
                    UserPromocode.is_active == True
                )
                .correlate(User)
                .scalar_subquery()
            )
            
            if order_direction == 'asc':
                return query.order_by(active_promocodes_count.asc())
            else:
                return query.order_by(active_promocodes_count.desc())
        
        # Для остальных колонок используем стандартную логику
        return super().apply_order_by(query, order_column, order_direction, **kwargs)


class CustomUserPromocodeSQLAInterface(SQLAInterface):
    """Кастомный SQLAInterface: сортировка по is_active_display → по колонке is_active"""

    def apply_order_by(self, query, order_column, order_direction, **kwargs):
        if order_column == "is_active_display":
            order_column = "is_active"
        return super().apply_order_by(query, order_column, order_direction, **kwargs)


class UserPromocodeInline(ModelView):
    """Инлайн-вьюха для активированных промокодов пользователя"""

    datamodel = CustomUserPromocodeSQLAInterface(UserPromocode)
    base_permissions = ['can_list', 'can_show']
    list_title = "Промокоды"

    list_columns = [
        "promocode.code",
        "promocode.services_summary",
        "promo_date_range",
        "is_active_display",
    ]
    order_columns = ["promocode.code", "is_active_display"]
    show_columns = [
        "promocode.code",
        "promocode.services_summary",
        "created_at_display",
        "promo_date_range",
        "remaining_balance_display",
        "is_active_display",
    ]
    show_fieldsets = [
        (
            "Промокод",
            {
                "fields": ["promocode.code", "promocode.services_summary"],
                "expanded": True,
            },
        ),
        (
            "Период действия",
            {
                "fields": ["created_at_display", "promo_date_range"],
                "expanded": True,
            },
        ),
        (
            "Остаток по услугам",
            {
                "fields": ["remaining_balance_display"],
                "expanded": True,
            },
        ),
        (
            "Статус",
            {
                "fields": ["is_active_display"],
                "expanded": True,
            },
        ),
    ]
    label_columns = {
        "promocode.code": "Промокод",
        "promocode.services_summary": "На что (услуги)",
        "created_at_display": "Дата активации",
        "promo_date_range": "Период действия (с — по)",
        "remaining_balance_display": "Остаток",
        "is_active_display": "Статус",
    }

    def get_query(self):
        return super().get_query().options(
            joinedload(UserPromocode.promocode).joinedload(Promocode.services),
            joinedload(UserPromocode.remaining_services),
        )


class UserAnalizePaymentInline(ModelView):
    """Инлайн-вьюха для покупок пользователя"""

    datamodel = SQLAInterface(UserAnalizePayment)
    base_permissions = ['can_list', 'can_show']
    list_title = "Покупки"

    list_columns = ["analize_payment.name", "is_active", "tranzaction_id"]
    label_columns = {
        "analize_payment.name": "Пакет",
        "is_active": "Активен",
        "tranzaction_id": "Транзакция",
    }


class UserModelView(ModelView):
    datamodel = CustomUserSQLAInterface(User)
    base_permissions = ['can_list', 'can_show']
    related_views = [UserPromocodeInline, UserAnalizePaymentInline]

    list_columns = [
        "id",
        "username",
        "player_username",
        "first_name",
        "last_name",
        "role",
        "active_promocodes",
        "active_payments",
        "total_balance",
    ]
    order_columns = ['id', 'username', 'role', 'active_promocodes']
    show_columns = list_columns

    label_columns = {
        "id": "ID",
        "username": "Username",
        "player_username": "Игровое имя",
        "first_name": "Имя",
        "last_name": "Фамилия",
        "role": "Роль",
        "active_promocodes": "Активные промокоды",
        "active_payments": "Покупки",
        "total_balance": "Общий баланс",
    }

    search_columns = ["id", "username", "player_username", "admin_insert_name"]
