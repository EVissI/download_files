from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.filters.user_info import UserInfo
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.excel_view import ExcelKeyboard
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.models import User

from bot.routers.admin.excel_view.general_unloading import general_unloading_router
from bot.routers.admin.excel_view.upload_by_user import user_unloading_router
from bot.routers.admin.excel_view.upload_by_user_gnu import detailed_user_unloading_router
from bot.routers.admin.excel_view.general_uploading_gnu import detailed_unloading_router

from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

excel_setup_router = Router()
excel_setup_router.include_routers(
    general_unloading_router,
    user_unloading_router,
    detailed_user_unloading_router,
    detailed_unloading_router
)


@excel_setup_router.message(F.text == MainKeyboard.get_admin_kb_text()['excel'],UserInfo())
async def handle_excel_setup(message: Message, state: FSMContext):
    """
    Handles the Excel setup command from the admin keyboard.
    """
    await message.answer(
        message.text,
        reply_markup=ExcelKeyboard.build()
    )
    await state.set_state(GeneralStates.excel_view)

@excel_setup_router.message(F.text == ExcelKeyboard.get_kb_text()['back'], StateFilter(GeneralStates.excel_view), UserInfo())
async def handle_excel_back(message: Message, state: FSMContext, i18n:TranslatorRunner, user_info: User):
    """
    Handles the back command in the Excel setup state.
    """
    await state.clear()
    await message.answer(
        message.text,
        reply_markup=MainKeyboard.build(user_info.role, i18n)
    )