from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.models.decorators import renders
from bot.db.models import User, UserPromocode, UserAnalizePayment, Promocode
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, select
from flask import request


class CustomUserSQLAInterface(SQLAInterface):
    """Кастомный SQLAInterface для обработки сортировки по промокодам"""
    
    def apply_order_by(self, query, order_column, order_direction, **kwargs):
        """Переопределяем сортировку для пропуска active_promocodes"""
        # Если сортировка по active_promocodes, пропускаем её здесь,
        # так как она уже применена в get_query()
        if order_column == 'active_promocodes':
            return query
        # Для остальных колонок применяем стандартную сортировку
        return super().apply_order_by(query, order_column, order_direction, **kwargs)


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
        else:
            # Для остальных случаев загружаем связанные данные через selectinload
            query = query.options(
                selectinload(User.used_promocodes).selectinload(UserPromocode.promocode),
                selectinload(User.used_promocodes).selectinload(UserPromocode.remaining_services),
                selectinload(User.analize_payments_assoc).selectinload(UserAnalizePayment.analize_payment),
                selectinload(User.analize_payments_assoc).selectinload(UserAnalizePayment.remaining_services),
            )
        
        return query
    
    def _get_list_widget(self, filters, order_column, order_direction, page=None, page_size=None, **kwargs):
        """Переопределяем для правильной загрузки данных при сортировке по промокодам"""
        widgets = super()._get_list_widget(
            filters=filters,
            order_column=order_column,
            order_direction=order_direction,
            page=page,
            page_size=page_size,
            **kwargs
        )
        
        # Если сортировка по промокодам, загружаем связанные данные отдельно
        if order_column == 'active_promocodes':
            try:
                # Получаем записи из виджета (они уже отсортированы через get_query())
                list_widget = None
                if isinstance(widgets, dict):
                    list_widget = widgets.get('list')
                elif hasattr(widgets, 'list'):
                    list_widget = widgets.list
                
                # Получаем список записей из виджета
                items = None
                if list_widget:
                    # Пробуем разные способы получить список
                    if hasattr(list_widget, '_list'):
                        items = list_widget._list
                    elif hasattr(list_widget, 'get_list'):
                        items = list_widget.get_list()
                    else:
                        # Если не можем получить из виджета, используем запрос напрямую
                        # но с применением сортировки из get_query()
                        query = self.get_query()
                        # Применяем фильтры через datamodel
                        if filters:
                            query = self.datamodel.apply_filters(query, filters)
                        # Применяем пагинацию
                        page_size_val = page_size or getattr(self, 'page_size', 20)
                        offset = (page or 0) * page_size_val
                        items = query.offset(offset).limit(page_size_val).all()
                
                if items:
                    # Получаем ID всех пользователей (сохраняя порядок из items)
                    user_ids = [item.id for item in items]
                    
                    # Загружаем связанные данные для всех записей отдельным запросом
                    users_with_data = (
                        self.datamodel.session.query(User)
                        .filter(User.id.in_(user_ids))
                        .options(
                            selectinload(User.used_promocodes).selectinload(UserPromocode.promocode),
                            selectinload(User.used_promocodes).selectinload(UserPromocode.remaining_services),
                            selectinload(User.analize_payments_assoc).selectinload(UserAnalizePayment.analize_payment),
                            selectinload(User.analize_payments_assoc).selectinload(UserAnalizePayment.remaining_services),
                        )
                        .all()
                    )
                    
                    # Создаем словарь для быстрого доступа
                    users_dict = {user.id: user for user in users_with_data}
                    
                    # Обновляем записи загруженными данными на месте
                    for item in items:
                        if item.id in users_dict:
                            loaded_user = users_dict[item.id]
                            # Копируем загруженные связанные данные
                            item.used_promocodes = loaded_user.used_promocodes
                            item.analize_payments_assoc = loaded_user.analize_payments_assoc
                    
                    # Пересортируем записи по промокодам (на случай, если порядок потерялся)
                    # Получаем направление сортировки
                    order_direction = order_direction or 'asc'
                    # Создаем функцию для получения значения промокода для сортировки
                    def get_promo_sort_key(user):
                        if user.used_promocodes:
                            active_promos = [p.promocode.code for p in user.used_promocodes if p.is_active]
                            if active_promos:
                                return min(active_promos)
                        return None
                    
                    # Сортируем записи
                    if order_direction == 'asc':
                        items.sort(key=lambda u: (get_promo_sort_key(u) is None, get_promo_sort_key(u)))
                    else:
                        items.sort(key=lambda u: (get_promo_sort_key(u) is None, get_promo_sort_key(u)), reverse=True)
                    
                    # Обновляем виджет с пересортированными данными
                    if list_widget and hasattr(list_widget, '_list'):
                        list_widget._list = items
            except Exception as e:
                # Если возникла ошибка, просто пропускаем загрузку данных
                # Это не критично - данные просто не будут отображаться
                pass
        
        return widgets
