from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from aiogram.filters import StateFilter

from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb

from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.dao import AnalizePaymentDAO
from bot.db.schemas import SAnalizePayment

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

create_payment_router = Router()

class PaymentCreateStates(StatesGroup):
    package_name = State()
    price = State()
    amount = State()

@create_payment_router.message(F.text == PaymentKeyboard.get_kb_text()['create'], StateFilter(GeneralStates.payment_view))
async def start_create_payment(message: Message, state: FSMContext, i18n: TranslatorRunner):
    await state.set_state(PaymentCreateStates.package_name)
    await message.answer("Введите название пакета (например: 10 Анализов):", reply_markup=get_cancel_kb(i18n))



@create_payment_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
                                StateFilter(PaymentCreateStates))
async def cancel_create_payment(message: Message, state: FSMContext, i18n: TranslatorRunner):
    await state.set_state(GeneralStates.payment_view)
    await message.answer(message.text, reply_markup=PaymentKeyboard.build(), parse_mode="HTML")

@create_payment_router.message(F.text, StateFilter(PaymentCreateStates.package_name))
async def get_package_name(message: Message, state: FSMContext):
    package_name = message.text.strip()
    await state.update_data(package_name=package_name)
    await state.set_state(PaymentCreateStates.amount)
    await message.answer("Введите кол-во анализов в пакете:")

@create_payment_router.message(F.text, StateFilter(PaymentCreateStates.amount))
async def get_amount(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число (целое число):")
        return
    await state.update_data(amount=int(message.text))
    await state.set_state(PaymentCreateStates.price)
    await message.answer("Введите цену пакета (в рублях):")

@create_payment_router.message(F.text, StateFilter(PaymentCreateStates.price))
async def get_price(message: Message, state: FSMContext,session_with_commit: AsyncSession):
    if not message.text.isdigit():
        await message.answer("Введите цену (целое число):")
        return
    data = await state.get_data()
    package_name = data.get('package_name')
    amount = data.get('amount')
    price = int(message.text)

    await AnalizePaymentDAO(session_with_commit).add(
        SAnalizePayment(
            name=package_name,
            price=price,
            amout=amount
        )
    )
    await state.set_state(GeneralStates.payment_view)
    await message.answer(f"Пакет '{package_name}' с {amount} анализами по цене {price} руб. успешно создан.",
                         reply_markup=PaymentKeyboard.build())