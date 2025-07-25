from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from loguru import logger
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.filters.user_info import UserInfo
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.db.dao import PromoCodeDAO
from bot.common.kbds.inline.activate_promo import PromoCallback
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.models import User
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

class ActivatePromoState(StatesGroup):
    promo_code = State()

activate_promo_router = Router()

@activate_promo_router.callback_query(PromoCallback.filter(F.action == "activate"))
async def handle_activate_promo(
    callback: CallbackQuery,
    state: FSMContext,
    i18n: TranslatorRunner
):
    """
    Handles the activation of a promo code.
    """
    try:
        await callback.message.delete()
        await state.set_state(ActivatePromoState.promo_code)
        await callback.message.answer(
            i18n.user.static.input_promo(),
            reply_markup=get_cancel_kb(i18n)
        )
    except Exception as e:
        logger.error(f"Error activating promo code: {e}")
        await callback.answer()

@activate_promo_router.message(F.text.in_(get_all_locales_for_key("keyboard-reply-cancel")), 
                               StateFilter(ActivatePromoState.promo_code), UserInfo())
async def cancel_promo_activation(
    message: Message,
    state: FSMContext,
    i18n: TranslatorRunner,
    user_info: User
):
    await state.clear()
    await message.answer(
        message.text,
        reply_markup=MainKeyboard.build(role=user_info.role, i18n=i18n)
    )

@activate_promo_router.message(StateFilter(ActivatePromoState.promo_code), F.text, UserInfo())
async def handle_promo_code_input(
    message: Message,
    state: FSMContext,
    session_without_commit: AsyncSession,
    i18n: TranslatorRunner,
    user_info: User
):
    """
    Handles the input of the promo code.
    """
    promo_code = message.text.strip()
    user_id = message.from_user.id

    try:
        promo_dao = PromoCodeDAO(session_without_commit)
        is_valid = await promo_dao.validate_promo_code(promo_code, user_id)

        if is_valid:
            is_activate = await promo_dao.activate_promo_code(promo_code, user_id)
            if is_activate:
                text = i18n.user.static.promo_activated()
            else:
                text = i18n.user.static.invalid_promo()
        else:
            text = i18n.user.static.invalid_promo()
    except Exception as e:
        logger.error(f"Error processing promo code: {e}")
        text = i18n.user.static.error_processing_promo()
    finally:
        await session_without_commit.commit()
        await message.answer(text, reply_markup=MainKeyboard.build(user_info.role, i18n))
        await state.clear()