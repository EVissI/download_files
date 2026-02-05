from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.models.decorators import renders
from bot.db.models import User, UserPromocode, UserAnalizePayment
from sqlalchemy.orm import joinedload
from sqlalchemy import func, select
from flask import request


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
    datamodel = SQLAInterface(User)
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
        """Переопределяем запрос для поддержки сортировки по активным промокодам"""
        query = super().get_query()
        
        # Проверяем параметры сортировки из запроса
        # Flask-AppBuilder может использовать разные форматы параметров
        order_column = request.args.get('order_column') or request.args.get('order_col')
        order_direction = request.args.get('order_direction', 'asc').lower()
        
        # Если запрошена сортировка по active_promocodes
        if order_column == 'active_promocodes':
            # Создаем подзапрос для подсчета активных промокодов
            # Используем корреляционный подзапрос для правильной работы с JOIN
            active_promocodes_count = (
                select(func.count(UserPromocode.id))
                .where(
                    UserPromocode.user_id == User.id,
                    UserPromocode.is_active == True
                )
                .correlate(User)
                .scalar_subquery()
            )
            
            # Применяем сортировку по подзапросу
            if order_direction == 'asc':
                query = query.order_by(active_promocodes_count.asc())
            else:
                query = query.order_by(active_promocodes_count.desc())
        
        return query
