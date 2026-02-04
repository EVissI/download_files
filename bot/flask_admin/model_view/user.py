from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.models.decorators import renders
from bot.db.models import User, UserPromocode, UserAnalizePayment, Promocode
from sqlalchemy.orm import joinedload
from sqlalchemy import func, select
from flask import request


class CustomUserSQLAInterface(SQLAInterface):
    """Кастомный SQLAInterface для обработки сортировки по промокодам"""
    
    def apply_order_by(self, query, order_column, order_direction):
        """Переопределяем сортировку для пропуска active_promocodes"""
        # Если сортировка по active_promocodes, пропускаем её здесь,
        # так как она уже применена в get_query()
        if order_column == 'active_promocodes':
            return query
        # Для остальных колонок применяем стандартную сортировку
        return super().apply_order_by(query, order_column, order_direction)


class UserPromocodeInline(ModelView):
    """Инлайн-вьюха для активированных промокодов пользователя"""

    datamodel = SQLAInterface(UserPromocode)
    base_permissions = ['can_list', 'can_show']

    list_columns = ["promocode.code", "is_active"]
    label_columns = {
        "promocode.code": "Промокод",
        "is_active": "Активен",
    }


class UserAnalizePaymentInline(ModelView):
    """Инлайн-вьюха для покупок пользователя"""

    datamodel = SQLAInterface(UserAnalizePayment)
    base_permissions = ['can_list', 'can_show']

    list_columns = ["analize_payment.name", "is_active", "tranzaction_id"]
    label_columns = {
        "analize_payment.name": "Пакет",
        "is_active": "Активен",
        "tranzaction_id": "Транзакция",
    }


class UserModelView(ModelView):
    datamodel = CustomUserSQLAInterface(User)
    base_permissions = ['can_list', 'can_show']
    
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

    search_columns = ["id", "username"]

    def get_query(self):
        """Переопределяем запрос для поддержки сортировки по промокодам"""
        query = super().get_query()
        query = query.options(
            joinedload(User.used_promocodes).joinedload(UserPromocode.promocode)
        )
        
        # Проверяем параметры сортировки (flask_appbuilder использует формат _oc_ViewName и _od_ViewName)
        order_column = None
        order_direction = 'asc'
        
        # Ищем параметры сортировки в разных форматах
        for key, value in request.args.items():
            if key.startswith('_oc_') or key == '_oc' or key == 'order_column':
                order_column = value
            elif key.startswith('_od_') or key == '_od' or key == 'order_direction':
                order_direction = value
        
        if order_column == 'active_promocodes':
            # Создаем подзапрос для сортировки по первому активному промокоду
            subquery = (
                select(
                    UserPromocode.user_id,
                    func.min(Promocode.code).label('min_promo_code')
                )
                .join(Promocode, UserPromocode.promocode_id == Promocode.id)
                .where(UserPromocode.is_active == True)
                .group_by(UserPromocode.user_id)
                .subquery()
            )
            
            query = query.outerjoin(subquery, User.id == subquery.c.user_id)
            
            if order_direction == 'asc':
                query = query.order_by(subquery.c.min_promo_code.asc().nullslast())
            else:
                query = query.order_by(subquery.c.min_promo_code.desc().nullslast())
        
        return query
