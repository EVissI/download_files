from aiogram import Router, F
from bot.common.filters.user_info import UserInfo
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.kbds.inline.back import BackCallback, get_back_kb
from bot.common.kbds.inline.profile import (
    ProfileCallback,
    ProfileChangeLanguageCallback,
    get_profile_change_language_kb,
    get_profile_kb,
)
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import UserDAO
from bot.db.models import User
from bot.db.schemas import SUser
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

profile_router = Router()


@profile_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-user-reply-profile")),
    UserInfo(),
)
async def profile_command(message: Message, user_info: User, i18n: TranslatorRunner):
    await message.answer(
        i18n.user.profile.text(
            player_username=user_info.player_username,
            analiz_balance=user_info.analiz_balance if user_info.analiz_balance is not None else '∞',
            lang_code=user_info.lang_code,
        ),
        reply_markup=get_profile_kb(i18n),
    )


@profile_router.callback_query(
    ProfileCallback.filter(F.action == "change_lang"), UserInfo()
)
async def change_language_callback(
    callback: CallbackQuery, user_info: User, i18n: TranslatorRunner
):
    await callback.message.edit_text(
        i18n.user.profile.change_language_text(),
        reply_markup=get_profile_change_language_kb(i18n),
    )


@profile_router.callback_query(
    ProfileChangeLanguageCallback.filter(F.action == "back"), UserInfo()
)
async def change_language_back_callback(
    callback: CallbackQuery, user_info: User, i18n: TranslatorRunner
):
    await callback.message.edit_text(
        i18n.user.profile.text(
            player_username=user_info.player_username,
            analiz_balance=user_info.analiz_balance if user_info.analiz_balance is not None else '∞',
            lang_code=user_info.lang_code,
        ),
        reply_markup=get_profile_kb(i18n),
    )


@profile_router.callback_query(
    ProfileChangeLanguageCallback.filter(F.action == "change_language"), UserInfo()
)
async def change_language_callback(
    callback: CallbackQuery,
    callback_data: ProfileChangeLanguageCallback,
    session_with_commit: AsyncSession,
    user_info: User,
    i18n: TranslatorRunner,
):
    await callback.message.delete()
    user_info.lang_code = callback_data.language
    await UserDAO(session_with_commit).update(
        user_info.id, SUser.model_validate(user_info.to_dict())
    )
    new_i18n: TranslatorRunner = translator_hub.get_translator_by_locale(
        callback_data.language
    )
    await callback.message.answer(
        new_i18n.user.profile.change_language.confirm(),
        reply_markup=MainKeyboard.build(user_info.role, new_i18n),
    )


@profile_router.callback_query(BackCallback.filter(F.context == "profile"), UserInfo())
async def back_to_profile(
    callback: CallbackQuery, user_info: User, i18n: TranslatorRunner
):
    await callback.message.edit_text(
        i18n.user.profile.text(
            player_username=user_info.player_username,
            analiz_balance=user_info.analiz_balance if user_info.analiz_balance is not None else '∞',
            lang_code=user_info.lang_code,
        ),
        reply_markup=get_profile_kb(i18n),
    )
