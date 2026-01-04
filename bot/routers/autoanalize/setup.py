from aiogram import Router, F
from aiogram.types import Message
from bot.routers.autoanalize.batch import batch_auto_analyze_router
from bot.common.utils.i18n import get_all_locales_for_key
from bot.routers.autoanalize.autoanaliz import auto_analyze_router
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.config import settings

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

setup_autoanalize_router = Router()

setup_autoanalize_router.include_routers( batch_auto_analyze_router, auto_analyze_router)

@auto_analyze_router.message(
    F.text.in_(
        get_all_locales_for_key(translator_hub, "keyboard-user-reply-autoanalyze")
    )
)
async def autoanalyze_command(
    message: Message,
    i18n: TranslatorRunner,
):  
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
        text=i18n.auto.analyze.single_match(), callback_data="autoanalyze_single"
    )
    keyboard.button(
        text=i18n.auto.analyze.batch_type(), callback_data="autoanalyze_batch"
    )
    keyboard.adjust(1)
    await message.answer(i18n.user.static.select_autoanalyze_type(), reply_markup=keyboard.as_markup())