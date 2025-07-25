from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO

deactivate_promo_router = Router()

class PromoDeactivateStates(StatesGroup):
    waiting_for_code = State()

@deactivate_promo_router.message(F.text == PromoKeyboard.get_kb_text()['deactivate_promo'])
async def start_deactivate_promo(message: Message, state: FSMContext):
    await state.set_state(PromoDeactivateStates.waiting_for_code)
    await message.answer("Введите код промокода для деактивации:")

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