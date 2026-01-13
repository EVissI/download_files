from flask_appbuilder import ModelView
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.models.decorators import renders
from bot.db.models import User, UserPromocode, UserAnalizePayment
from sqlalchemy.orm import joinedload


class UserPromocodeInline(ModelView):
    """Инлайн-вьюха для активированных промокодов пользователя"""

    datamodel = SQLAInterface(UserPromocode)
    can_create = False
    can_edit = False
    can_delete = False
    can_show = False
    can_list = True

    list_columns = ["promocode.code", "is_active"]
    label_columns = {
        "promocode.code": "Промокод",
        "is_active": "Активен",
    }


class UserAnalizePaymentInline(ModelView):
    """Инлайн-вьюха для покупок пользователя"""

    datamodel = SQLAInterface(UserAnalizePayment)
    can_create = False
    can_edit = False
    can_delete = False
    can_show = False
    can_list = True

    list_columns = ["analize_payment.name", "is_active", "tranzaction_id"]
    label_columns = {
        "analize_payment.name": "Пакет",
        "is_active": "Активен",
        "tranzaction_id": "Транзакция",
    }


class UserModelView(ModelView):
    datamodel = SQLAInterface(User)

    # Только просмотр
    can_create = False
    can_edit = False
    can_delete = False

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

    search_columns = ["username", "first_name", "last_name", "player_username"]

    related_views = [UserPromocodeInline, UserAnalizePaymentInline]

    def get_query(self):
        return (
            super()
            .get_query()
            .options(
                joinedload(User.used_promocodes).joinedload(
                    UserPromocode.remaining_services
                ),
                joinedload(User.analize_payments_assoc).joinedload(
                    UserAnalizePayment.remaining_services
                ),
                joinedload(User.used_promocodes).joinedload(UserPromocode.promocode),
                joinedload(User.analize_payments_assoc).joinedload(
                    UserAnalizePayment.analize_payment
                ),
            )
        )

    def get_count_query(self):
        return (
            super()
            .get_count_query()
            .options(
                joinedload(User.used_promocodes),
                joinedload(User.analize_payments_assoc),
            )
        )

    @renders("active_promocodes")
    def active_promocodes(self, item):
        """Отображение активных промокодов"""
        active = [up for up in item.used_promocodes if up.is_active]
        if not active:
            return "—"
        return ", ".join([up.promocode.code for up in active])

    @renders("active_payments")
    def active_payments(self, item):
        """Отображение активных покупок"""
        active = [uap for uap in item.analize_payments_assoc if uap.is_active]
        if not active:
            return "—"
        return ", ".join([uap.analize_payment.name for uap in active])

    @renders("total_balance")
    def total_balance(self, item):
        """Общий баланс по всем активным сервисам"""
        total = 0
        # Из промокодов
        for up in item.used_promocodes:
            if up.is_active:
                for rs in up.remaining_services:
                    if rs.remaining_quantity:
                        total += rs.remaining_quantity
        # Из покупок
        for uap in item.analize_payments_assoc:
            if uap.is_active:
                for rs in uap.remaining_services:
                    total += rs.remaining_quantity
        return total
