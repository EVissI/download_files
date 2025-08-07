from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.func.func import split_message
from bot.common.kbds.inline.back import BackCallback, get_back_kb
from bot.common.kbds.inline.paginate import PaginatedCallback, get_paginated_keyboard
from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.db.dao import UserAnalizePaymentDAO, UserDAO
from bot.db.models import User

def get_user_display_text(user: User) -> str:
    """
    Возвращает отображаемый текст для пользователя.
    """
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    username = f"@{user.username}" if user.username else "без имени"
    return name or username

def get_user_id(user: User) -> int:
    """
    Возвращает ID пользователя.
    """
    return user.id


view_buyers_router = Router()

@view_buyers_router.message(F.text == PaymentKeyboard.get_kb_text()['view_buyers'])
async def handle_view_buyers(message: Message,session_without_commit: AsyncSession):
    try:
        users = UserDAO(session_without_commit).find_one_or_none_by_id(message.from_user.id)
        if not users:
            await message.answer("Пользователи не найдены.")
            return

        # Создание клавиатуры
        keyboard = get_paginated_keyboard(
            items=users,
            context="user_list",
            get_display_text=get_user_display_text,
            get_item_id=get_user_id,
            page=0,
            items_per_page=5,
        )

        await message.answer("Список пользователей:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        await message.answer("Произошла ошибка при загрузке списка пользователей.")

@view_buyers_router.callback_query(PaginatedCallback.filter(F.context == "user_list"))
async def handle_user_pagination(callback: CallbackQuery, callback_data: PaginatedCallback, i18n, session_without_commit):
    try: 

        if callback_data.action == "select":
            user_id = callback_data.item_id
            user_dao = UserDAO(session_without_commit)
            user = await user_dao.find_one_or_none_by_id(user_id)
            if user:
                display_text = 'Пользователь: ' + get_user_display_text(user) + '\n'
                buyed_pacage = await UserAnalizePaymentDAO(session_without_commit).get_all_by_user(user_id)
                if buyed_pacage:
                    display_text += f"\nКупленные пакеты: {'\n\n'.join([f'{p.analize_payment.name} за {p.analize_payment.price} RUB' for p in buyed_pacage])}"
                for message in split_message(display_text, False):
                    if message.index == len(split_message(display_text, False)):
                        await callback.message.answer(
                            reply_markup=get_back_kb(i18n, "user_buyed_pacage_list"),
                        )
                    else:
                        await callback.message.answer(message)
        elif callback_data.action in ["prev", "next"]:
            user_dao = UserDAO(session_without_commit)
            users = await user_dao.get_users_with_payments() 
            keyboard = get_paginated_keyboard(
                items=users,
                context="user_list",
                get_display_text=get_user_display_text,
                get_item_id=get_user_id,
                page=callback_data.page,
                items_per_page=5,
                lang="ru"
            )
            await callback.message.edit_reply_markup(reply_markup=keyboard)

        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при обработке коллбэка пагинации: {e}")
        await callback.message.answer("Произошла ошибка при обработке действия.")

@view_buyers_router.message(BackCallback.filter(F.context == "user_buyed_pacage_list"))
async def handle_back_to_user_list(message: Message, session_without_commit: AsyncSession):
    user_dao = UserDAO(session_without_commit)
    users = await user_dao.get_users_with_payments()
    keyboard = get_paginated_keyboard(
        items=users,
        context="user_list",
        get_display_text=get_user_display_text,
        get_item_id=get_user_id,
        page=0,
        items_per_page=5,
        lang="ru"
    )
    await message.answer("Список пользователей:", reply_markup=keyboard)