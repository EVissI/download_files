from aiogram import Router, F
from aiogram.types import Message
from bot.common.filters.user_info import UserInfo
from bot.routers.autoanalize.batch import batch_auto_analyze_router
from bot.common.utils.i18n import get_all_locales_for_key
from bot.routers.autoanalize.autoanaliz import auto_analyze_router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from bot.db.dao import MessagesTextsDAO
from bot.db.models import User
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.config import settings

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

setup_autoanalize_router = Router()

setup_autoanalize_router.include_routers(batch_auto_analyze_router, auto_analyze_router)

@auto_analyze_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-autoanalyze")
    ), UserInfo()
)
async def autoanalyze_command(
    message: Message,
    i18n: TranslatorRunner,
    user_info: User,
    session_without_commit: AsyncSession,
):
    message_dao =   MessagesTextsDAO(session_without_commit)
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text=await message_dao.get_text('analyze_solo_single_b', user_info.lang_code), callback_data="autoanalyze_single"
    )
    keyboard.button(
        text=await message_dao.get_text('analyze_solo_batch_b', user_info.lang_code), callback_data="autoanalyze_batch"
    )
    keyboard.adjust(1)
    await message.answer(await message_dao.get_text('select_autoanalyze_type', user_info.lang_code), reply_markup=keyboard.as_markup())