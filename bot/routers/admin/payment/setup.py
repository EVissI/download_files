from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.routers.admin.payment.create import create_payment_router
from bot.routers.admin.payment.delete import delete_payment_router
from bot.routers.admin.payment.view import view_payment_router
from bot.routers.admin.payment.view_buyers import view_buyers_router

payment_setup_router = Router()
payment_setup_router.include_routers(
    delete_payment_router,
    create_payment_router,
    view_payment_router,
    view_buyers_router
)
@payment_setup_router.message(F.text == AdminKeyboard.get_kb_text()['payment'], StateFilter(GeneralStates.admin_panel))
async def handle_payment(message: Message, state: FSMContext):
    await state.set_state(GeneralStates.payment_view)
    await message.answer(message.text, reply_markup=PaymentKeyboard.build())

@payment_setup_router.message(F.text == PaymentKeyboard.get_kb_text()['back'], StateFilter(GeneralStates.payment_view))
async def handle_back(message: Message, state: FSMContext):
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(message.text, reply_markup=AdminKeyboard.build())