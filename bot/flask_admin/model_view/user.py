import asyncio

from aiogram import Bot
from flask import flash, redirect, request, url_for
from flask_appbuilder import ModelView, expose, has_access, permission_name
from flask_appbuilder.models.sqla.interface import SQLAInterface
from bot.db.models import (
    ContentCard,
    Promocode,
    User,
    UserAnalizePayment,
    UserContentCard,
    UserPromocode,
)
from bot.config import create_bot_for_sync_context
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload


def _run_telegram_sync(action):
    async def _runner() -> None:
        tg_bot = create_bot_for_sync_context()
        try:
            await action(tg_bot)
        finally:
            await tg_bot.session.close()

    asyncio.run(_runner())


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
    show_template = "show_user.html"

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

    def render_template(self, template, **kwargs):
        kwargs.setdefault(
            "user_fab_endpoint", getattr(self, "endpoint", self.__class__.__name__)
        )
        return super().render_template(template, **kwargs)

    @expose("/grant_cards/<int:pk>", methods=["POST"])
    @has_access
    @permission_name("show")
    def grant_cards(self, pk: int):
        user = self.datamodel.get(pk)
        if not user:
            flash("Пользователь не найден", "danger")
            return redirect(url_for(f"{self.endpoint}.list"))

        raw_qty = (request.form.get("cards_quantity") or "").strip()
        try:
            cards_quantity = int(raw_qty)
        except (TypeError, ValueError):
            cards_quantity = 0

        if cards_quantity <= 0:
            flash("Введите корректное количество карточек (целое число > 0).", "warning")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        session = self.datamodel.session
        issued_count = 0
        try:
            all_card_ids_result = session.execute(
                select(ContentCard.id).order_by(ContentCard.id.asc())
            )
            all_card_ids = [
                row[0] for row in all_card_ids_result.all() if row[0] is not None
            ]
            if not all_card_ids:
                flash("В системе нет карточек для выдачи.", "warning")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

            existing_card_ids_result = session.execute(
                select(UserContentCard.content_card_id).where(
                    UserContentCard.user_id == pk
                )
            )
            existing_card_ids = {
                row[0] for row in existing_card_ids_result.all() if row[0] is not None
            }

            available_card_ids = [
                card_id for card_id in all_card_ids if card_id not in existing_card_ids
            ]
            if not available_card_ids:
                flash("У пользователя уже есть все доступные карточки.", "warning")
                return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

            to_issue_ids = available_card_ids[:cards_quantity]
            for card_id in to_issue_ids:
                session.add(UserContentCard(user_id=pk, content_card_id=card_id))
            session.commit()
            issued_count = len(to_issue_ids)
        except SQLAlchemyError as e:
            session.rollback()
            flash(f"Ошибка выдачи карточек: {e}", "danger")
            return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))

        if issued_count > 0:
            try:
                async def _send(tg_bot: Bot) -> None:
                    await tg_bot.send_message(
                        chat_id=pk,
                        text=(
                            f"Вам зачислено {issued_count} карточек.\n"
                            "Посмотрите их в личном кабинете по команде /cards."
                        ),
                    )

                _run_telegram_sync(_send)
            except Exception as e:
                flash(f"Карточки выданы, но сообщение в Telegram не отправлено: {e}", "warning")

        if issued_count < cards_quantity:
            flash(
                f"Выдано {issued_count} карточек из {cards_quantity}: больше доступных карточек нет.",
                "warning",
            )
        else:
            flash(f"Пользователю выдано {issued_count} карточек.", "success")

        return redirect(url_for(f"{self.endpoint}.show", pk=str(pk)))
