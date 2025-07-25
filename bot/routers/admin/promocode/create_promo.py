from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO
from bot.db.models import Promocode
from bot.db.schemas import SPromocode
promo_create_router = Router()

class PromoCreateStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_days = State()
    waiting_for_max_usage = State()

@promo_create_router.message(F.text == PromoKeyboard.get_kb_text()['create_promo'])
async def start_create_promo(message: Message, state: FSMContext):
    await state.set_state(PromoCreateStates.waiting_for_code)
    await message.answer("Введите название промокода(например: Happy2025):")

@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_code))
async def get_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await state.set_state(PromoCreateStates.waiting_for_days)
    await message.answer("Введите количество дней действия промокода:")

@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_days))
async def get_days(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число дней (целое число):")
        return
    await state.update_data(discount_days=int(message.text))
    await state.set_state(PromoCreateStates.waiting_for_max_usage)
    await message.answer("Введите максимальное количество использований (или 0 для неограниченного):")

@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_max_usage))
async def get_max_usage(message: Message, state: FSMContext, session_without_commit):
    if not message.text.isdigit():
        await message.answer("Введите число использований (целое число):")
        return
    max_usage = int(message.text)
    data = await state.get_data()
    code = data["code"]
    discount_days = data["discount_days"]

    promocode = SPromocode(
        code=code,
        discount_days=discount_days,
        is_active=True,
        max_usage=max_usage if max_usage > 0 else None,
        activate_count=0
    )
    dao = PromoCodeDAO(session_without_commit)
    await dao.add(promocode)
    await session_without_commit.commit()
    await message.answer(f"Промокод <b>{code}</b> создан!", parse_mode="HTML", reply_markup=PromoKeyboard.build())
    await state.set_state(GeneralStates.promo_view) 