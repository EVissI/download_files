from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.promo_code import PromoKeyboard

promo_setup_router = Router()

@promo_setup_router.message.filter(F.text == AdminKeyboard.get_kb_text()['promo'], StateFilter(GeneralStates.promo_view))
async def handle_back(message: Message, state: FSMContext):
    await state.set_state(GeneralStates.promo_view)
    await message.answer(message.text, reply_markup=PromoKeyboard.build())

@promo_setup_router.message.filter(F.text == PromoKeyboard.get_kb_text()['back'], StateFilter(GeneralStates.promo_view))
async def handle_back(message: Message, state: FSMContext):
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(message.text, reply_markup=AdminKeyboard.build())