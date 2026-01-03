from aiogram import Router,F
from aiogram.filters import StateFilter
from aiogram.types import Message
from bot.common.filters.role_filter import RoleFilter
from bot.common.filters.user_info import UserInfo
from bot.common.general_states import GeneralStates
from aiogram.fsm.context import FSMContext
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.models import User
from bot.routers.admin.command_router import commands_router
from bot.routers.admin.excel_view.setup import excel_setup_router
from bot.routers.admin.promocode.setup import promo_setup_router
from bot.routers.admin.payment.setup import payment_setup_router
from bot.routers.admin.notify import broadcast_router
from bot.routers.admin.users_setting.setup import user_setting_router
from bot.routers.admin.update_message_for_new import message_for_new_router
from bot.routers.admin.user_group import user_group_router
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

admin_setup_router = Router()
admin_setup_router.message.filter(RoleFilter(
                                        User.Role.ADMIN.value
                                        ))
admin_setup_router.include_routers(
    commands_router,
    excel_setup_router,
    promo_setup_router,
    payment_setup_router,
    broadcast_router,
    user_setting_router,
    message_for_new_router,
    user_group_router
)

@admin_setup_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-admin-reply-admin_panel")))
async def handle_admin_panel(message: Message, state: FSMContext):
    """
    Handles the admin panel command from the main keyboard.
    """
    await message.answer(
        "Выберите раздел или используйте кнопку ниже для входа в веб-админку:",
        reply_markup=AdminKeyboard.get_inline_admin_web()
    )
    await message.answer(
        "Разделы управления:",
        reply_markup=AdminKeyboard.build()
    )
    await state.set_state(GeneralStates.admin_panel)

@admin_setup_router.message(F.text == AdminKeyboard.get_kb_text()['back'], StateFilter(GeneralStates.admin_panel), UserInfo())
async def handle_admin_back(message: Message, state: FSMContext, i18n: TranslatorRunner, user_info: User):
    """
    Handles the back command in the admin panel state.
    """
    await state.set_state(None)
    await message.answer(
        message.text,
        reply_markup=MainKeyboard.build(user_info.role, i18n)
    )