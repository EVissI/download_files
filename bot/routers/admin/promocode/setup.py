from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.promo_code import PromoKeyboard

from bot.routers.admin.promocode.create_promo import promo_create_router
from bot.routers.admin.promocode.view_promo import view_promo_router
from bot.routers.admin.promocode.delete_promo import deactivate_promo_router

promo_setup_router = Router()
promo_setup_router.include_routers(
    promo_create_router,
    view_promo_router,
    deactivate_promo_router,
)

@promo_setup_router.message(F.text == AdminKeyboard.get_kb_text()['promo'], StateFilter(GeneralStates.admin_panel))
async def handle_back(message: Message, state: FSMContext):
    await state.set_state(GeneralStates.promo_view)
    await message.answer(message.text, reply_markup=PromoKeyboard.build())

@promo_setup_router.message(F.text == PromoKeyboard.get_kb_text()['back'], StateFilter(GeneralStates.promo_view))
async def handle_back(message: Message, state: FSMContext):
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(message.text, reply_markup=AdminKeyboard.build())