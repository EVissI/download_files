from flask import Flask
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_sqlalchemy import SQLAlchemy

from bot.db.models import (
    User,
    UserGroup,
    UserInGroup,
    Promocode,
    PromocodeServiceQuantity,
    UserPromocode,
    UserPromocodeService,
    MessageForNew,
    AnalizePayment,
    AnalizePaymentServiceQuantity,
    UserAnalizePayment,
    UserAnalizePaymentService,
)


def setup_admin(app: Flask, db: SQLAlchemy):
    """Инициализация Flask-Admin с ModelView для моделей"""

    admin = Admin(app, name="Admin Panel", template_mode="bootstrap4")

    # === ПОЛЬЗОВАТЕЛИ И ГРУППЫ ===

    class UserAdmin(ModelView):
        column_list = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "lang_code",
        )
        column_searchable_list = ("username", "first_name", "last_name", "email")
        column_filters = ("role", "lang_code")
        can_export = True
        page_size = 20

    class UserGroupAdmin(ModelView):
        column_list = ("id", "name", "users")
        column_searchable_list = ("name",)
        can_export = True

    class UserInGroupAdmin(ModelView):
        column_list = ("id", "user_id", "group_id", "user", "group")
        column_filters = ("group",)

    # === ПРОМОКОДЫ ===

    class PromocodeAdmin(ModelView):
        column_list = (
            "id",
            "code",
            "is_active",
            "max_usage",
            "activate_count",
            "duration_days",
        )
        column_searchable_list = ("code",)
        column_filters = ("is_active",)
        can_export = True

    class PromocodeServiceQuantityAdmin(ModelView):
        column_list = ("id", "promocode_id", "service_type", "quantity")
        column_filters = ("service_type",)

    class UserPromocodeAdmin(ModelView):
        column_list = ("id", "user_id", "promocode_id", "is_active")
        column_filters = ("is_active",)

    class UserPromocodeServiceAdmin(ModelView):
        column_list = ("id", "user_promocode_id", "service_type", "remaining_quantity")
        column_filters = ("service_type",)

    # === РАССЫЛКИ НОВЫМ ПОЛЬЗОВАТЕЛЯМ ===

    class MessageForNewAdmin(ModelView):
        column_list = ("id", "text", "lang_code", "dispatch_day", "dispatch_time")
        column_searchable_list = ("text", "dispatch_day")
        column_filters = ("lang_code", "dispatch_day")
        can_export = True
        page_size = 20

    # === ПЛАТЕЖИ АНАЛИЗОВ ===

    class AnalizePaymentAdmin(ModelView):
        column_list = ("id", "name", "price", "duration_days", "is_active")
        column_searchable_list = ("name",)
        column_filters = ("is_active",)
        can_export = True

    class AnalizePaymentServiceQuantityAdmin(ModelView):
        column_list = ("id", "analize_payment_id", "service_type", "quantity")
        column_filters = ("service_type",)

    class UserAnalizePaymentAdmin(ModelView):
        column_list = (
            "id",
            "user_id",
            "analize_payment_id",
            "tranzaction_id",
            "is_active",
        )
        column_searchable_list = ("tranzaction_id",)
        column_filters = ("is_active",)

    class UserAnalizePaymentServiceAdmin(ModelView):
        column_list = (
            "id",
            "user_analize_payment_id",
            "service_type",
            "remaining_quantity",
        )
        column_filters = ("service_type",)

    # === РЕГИСТРАЦИЯ МОДЕЛЕЙ ===

    # Пользователи
    admin.add_view(
        UserAdmin(User, db.session, name="Пользователи", category="Пользователи")
    )
    admin.add_view(
        UserGroupAdmin(UserGroup, db.session, name="Группы", category="Пользователи")
    )
    admin.add_view(
        UserInGroupAdmin(
            UserInGroup,
            db.session,
            name="Пользователи в группах",
            category="Пользователи",
        )
    )

    # Промокоды
    admin.add_view(
        PromocodeAdmin(Promocode, db.session, name="Промокоды", category="Промокоды")
    )
    admin.add_view(
        PromocodeServiceQuantityAdmin(
            PromocodeServiceQuantity,
            db.session,
            name="Услуги промокодов",
            category="Промокоды",
        )
    )
    admin.add_view(
        UserPromocodeAdmin(
            UserPromocode,
            db.session,
            name="Промокоды пользователей",
            category="Промокоды",
        )
    )
    admin.add_view(
        UserPromocodeServiceAdmin(
            UserPromocodeService,
            db.session,
            name="Услуги пользователей",
            category="Промокоды",
        )
    )

    # Сообщения для новых
    admin.add_view(
        MessageForNewAdmin(
            MessageForNew, db.session, name="Сообщения для новых", category="Рассылки"
        )
    )

    # Платежи анализов
    admin.add_view(
        AnalizePaymentAdmin(
            AnalizePayment, db.session, name="Платежи анализов", category="Анализы"
        )
    )
    admin.add_view(
        AnalizePaymentServiceQuantityAdmin(
            AnalizePaymentServiceQuantity,
            db.session,
            name="Услуги платежей",
            category="Анализы",
        )
    )
    admin.add_view(
        UserAnalizePaymentAdmin(
            UserAnalizePayment,
            db.session,
            name="Платежи пользователей",
            category="Анализы",
        )
    )
    admin.add_view(
        UserAnalizePaymentServiceAdmin(
            UserAnalizePaymentService,
            db.session,
            name="Услуги платежей пользователей",
            category="Анализы",
        )
    )

    return admin
