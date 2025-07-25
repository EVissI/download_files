from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

deactivate_promo_router = Router()

class PromoDeactivateStates(StatesGroup):
    waiting_for_code = State()

@deactivate_promo_router.message(F.text == PromoKeyboard.get_kb_text()['deactivate_promo'], StateFilter(GeneralStates.promo_view))
async def start_deactivate_promo(message: Message, state: FSMContext,i18n: TranslatorRunner):
    await state.set_state(PromoDeactivateStates.waiting_for_code)
    await message.answer("Введите код промокода для деактивации:", reply_markup=get_cancel_kb(i18n))

@deactivate_promo_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
                                    StateFilter(PromoDeactivateStates))
async def cancel_deactivate_promo(message: Message, state: FSMContext, i18n: TranslatorRunner):
    await state.set_state(GeneralStates.promo_view)
    await message.answer("Деактивация промокода отменена.", reply_markup=PromoKeyboard.build(), parse_mode="HTML")
    
@deactivate_promo_router.message(StateFilter(PromoDeactivateStates.waiting_for_code))
async def deactivate_code(message: Message, state: FSMContext, session_without_commit):
    code = message.text.strip()
    dao = PromoCodeDAO(session_without_commit)
    promocode = await dao.find_by_code(code)
    if not promocode:
        await message.answer("Промокод не найден.")
        return
    promocode.is_active = False
    await session_without_commit.commit()
    await message.answer(f"Промокод <b>{code}</b> деактивирован.", parse_mode="HTML", reply_markup=PromoKeyboard.build())
    await state.set_state(GeneralStates.promo_view)