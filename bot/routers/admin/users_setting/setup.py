from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.common.kbds.inline.user_settings import get_user_settings_kb, UserSettingsCallback
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.db.models import User
from bot.db.dao import UserDAO
from bot.common.kbds.inline.paginate import PaginatedCallback, get_paginated_keyboard
from bot.routers.admin.users_setting.update_username import user_list_update_username_router
from bot.routers.admin.users_setting.notify import user_setting_notify_router
from bot.routers.admin.users_setting.excel import user_settings_excel_router

user_setting_router = Router()
user_setting_router.include_routers(
    user_list_update_username_router,user_setting_notify_router,user_settings_excel_router
)

def create_message_for_user(user: User) -> str:
    return (
        f"ID: {user.id}\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Имя: {user.first_name or 'нет'}\n"
        f"Фамилия: {user.last_name or 'нет'}\n"
        f"Роль: {user.role}\n"
        f"Язык: {user.lang_code or 'не установлен'}\n"
        f"Поставленное имя: {user.admin_insert_name or 'не установлен'}"
    )

@user_setting_router.message(F.text == AdminKeyboard.admin_text_kb['users_setting'])
async def handle_user_settings(message: Message, session_without_commit):
    users = await UserDAO(session_without_commit).find_all()
    if not users:
        await message.answer("Пользователи не найдены.")
        return
    keyboard = get_paginated_keyboard(
        items=users,
        context="user_settings",
        get_display_text=lambda user: f"{user.admin_insert_name or user.username or user.id}",
        get_item_id=lambda user: user.id,
        page=0,
        items_per_page=5,
    )
    await message.answer("Список пользователей:", reply_markup=keyboard)

@user_setting_router.callback_query(PaginatedCallback.filter(F.context == "user_settings"))
async def handle_user_settings_pagination(callback: CallbackQuery, callback_data: PaginatedCallback, session_without_commit):
    if callback_data.action == "select":
        await callback.message.delete()
        user_id = callback_data.item_id
        user = await UserDAO(session_without_commit).find_one_or_none_by_id(user_id)
        await callback.message.answer(
            create_message_for_user(user),
            reply_markup=get_user_settings_kb(user_id)
        )
    else:
        keyboard = get_paginated_keyboard(
            items=await UserDAO(session_without_commit).find_all(),
            context="user_settings",
            get_display_text=lambda user: f"{user.admin_insert_name or user.username or user.id}",
            get_item_id=lambda user: user.id,
            page=callback_data.page,
            items_per_page=5,
        )
        await callback.message.edit_reply_markup(reply_markup=keyboard)

@user_setting_router.callback_query(UserSettingsCallback.filter(F.action == "back"))
async def handle_user_settings_back(callback: CallbackQuery, session_without_commit):
    users = await UserDAO(session_without_commit).find_all()
    if not users:
        await callback.message.answer("Пользователи не найдены.")
        return
    keyboard = get_paginated_keyboard(
        items=users,
        context="user_settings",
        get_display_text=lambda user: f"{user.admin_insert_name or user.username or user.id}",
        get_item_id=lambda user: user.id,
        page=0,
        items_per_page=5,
    )
    await callback.message.edit_text("Список пользователей:", reply_markup=keyboard)

