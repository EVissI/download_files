from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery

from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb

from bot.common.kbds.markup.payment_kb import PaymentKeyboard
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.db.dao import AnalizePaymentDAO, PromocodeServiceQuantityDAO
from bot.db.schemas import SAnalizePayment, SAnalizePaymentServiceQuantity
from bot.db.models import AnalizePaymentServiceQuantity

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

create_payment_router = Router()


class PaymentCreateStates(StatesGroup):
    package_name = State()
    price = State()
    amount = State()
    duration = State()  # новое состояние
    waiting_for_service_type = State()
    waiting_for_service_quantity = State()
    waiting_for_add_more_services = State()


@create_payment_router.message(
    F.text == PaymentKeyboard.get_kb_text()["create"],
    StateFilter(GeneralStates.payment_view),
)
async def start_create_payment(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.set_state(PaymentCreateStates.package_name)
    await message.answer(
        "Введите название пакета (например: 10 Анализов):",
        reply_markup=get_cancel_kb(i18n),
    )


@create_payment_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
    StateFilter(PaymentCreateStates),
)
async def cancel_create_payment(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.clear()
    await state.set_state(GeneralStates.payment_view)
    await message.answer(
        message.text, reply_markup=PaymentKeyboard.build(), parse_mode="HTML"
    )


@create_payment_router.message(F.text, StateFilter(PaymentCreateStates.package_name))
async def get_package_name(message: Message, state: FSMContext):
    package_name = message.text.strip()
    await state.update_data(package_name=package_name)
    await state.set_state(PaymentCreateStates.waiting_for_service_type)

    # Генерация инлайн-кнопок для выбора типа услуги
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=service_type.value,
                    callback_data=f"service_type:{service_type.name}",
                )
            ]
            for service_type in AnalizePaymentServiceQuantity.PaymentServiceType
        ]
    )

    await message.answer(
        "Выберите тип услуги для пакета:",
        reply_markup=keyboard,
    )


@create_payment_router.callback_query(
    StateFilter(PaymentCreateStates.waiting_for_service_type),
    F.data.startswith("service_type:"),
)
async def select_service_type(callback: CallbackQuery, state: FSMContext):
    service_type_name = callback.data.split(":")[1]  # Получаем имя (например, ANALYSIS)
    service_type = AnalizePaymentServiceQuantity.PaymentServiceType[
        service_type_name
    ]  # Преобразуем в перечисление

    await callback.message.delete()
    data = await state.get_data()
    services = data.get("services", [])
    services.append(
        {"service_type": service_type.name, "quantity": 0}
    )  # Сохраняем тип услуги
    await state.update_data(services=services)

    await state.set_state(PaymentCreateStates.waiting_for_service_quantity)
    await callback.message.answer(
        f"Введите количество для <b>{service_type.value}</b>:",
        parse_mode="HTML",
    )
    await callback.answer()


@create_payment_router.message(
    StateFilter(PaymentCreateStates.waiting_for_service_quantity)
)
async def get_service_quantity(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число (целое число):")
        return

    quantity = int(message.text)
    data = await state.get_data()
    services = data["services"]
    services[-1]["quantity"] = quantity
    await state.update_data(services=services)

    # Проверяем, остались ли ещё типы услуг, которые можно добавить
    existing_services = {service["service_type"] for service in services}

    remaining_services = [
        service_type
        for service_type in AnalizePaymentServiceQuantity.PaymentServiceType
        if service_type.name not in existing_services
    ]

    if not remaining_services:  # Если все типы уже добавлены
        await state.set_state(PaymentCreateStates.price)
        await message.answer("Введите цену пакета (в рублях):")
        return

    await state.set_state(PaymentCreateStates.waiting_for_add_more_services)

    # Генерация кнопок "да/нет"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="add_more_services:yes"),
                InlineKeyboardButton(text="Нет", callback_data="add_more_services:no"),
            ]
        ]
    )

    await message.answer("Хотите добавить ещё одну услугу?", reply_markup=keyboard)


@create_payment_router.callback_query(
    StateFilter(PaymentCreateStates.waiting_for_add_more_services),
    F.data.startswith("add_more_services:"),
)
async def add_more_services(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    await callback.message.delete()

    if choice == "yes":
        await state.set_state(PaymentCreateStates.waiting_for_service_type)

        # Генерация инлайн-кнопок для выбора типа услуги
        data = await state.get_data()
        existing_services = {
            service["service_type"] for service in data.get("services", [])
        }

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=service_type.value,
                        callback_data=f"service_type:{service_type.name}",
                    )
                ]
                for service_type in AnalizePaymentServiceQuantity.PaymentServiceType
                if service_type.name
                not in existing_services  # Исключаем уже добавленные типы
            ]
        )

        await callback.message.answer(
            "Выберите тип следующей услуги:",
            reply_markup=keyboard,
        )
    else:
        await state.set_state(PaymentCreateStates.price)
        await callback.message.answer("Введите цену пакета (в рублях):")


@create_payment_router.message(F.text, StateFilter(PaymentCreateStates.price))
async def get_price(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите цену (целое число):")
        return
    await state.update_data(price=int(message.text))
    await state.set_state(PaymentCreateStates.duration)
    await message.answer("Введите срок действия пакета в днях (0 — бессрочно):")


@create_payment_router.message(F.text, StateFilter(PaymentCreateStates.duration))
async def get_duration_days(
    message: Message, state: FSMContext, session_with_commit: AsyncSession
):
    if not message.text.isdigit():
        await message.answer("Введите срок действия (целое число):")
        return

    duration_days = int(message.text)
    data = await state.get_data()
    package_name = data.get("package_name")
    price = data.get("price")
    services = data.get("services")

    # Создание объекта SAnalizePayment
    payment_data = SAnalizePayment(
        name=package_name,
        price=price,
        duration_days=duration_days if duration_days > 0 else None,
        is_active=True,
    )

    # Сохранение в базе данных
    payment_dao = AnalizePaymentDAO(session_with_commit)
    service_dao = PromocodeServiceQuantityDAO(session_with_commit)
    payment = await payment_dao.add(payment_data)
    service_objects = [
        SAnalizePaymentServiceQuantity(
            analize_payment_id=payment.id,
            service_type=service["service_type"],
            quantity=service["quantity"],
        )
        for service in services
    ]
    for service in service_objects:
        await service_dao.add(service)

    services_text = ", ".join(
        [
            f"{AnalizePaymentServiceQuantity.PaymentServiceType[service.service_type].value} ({service.quantity})"
            for service in service_objects
        ]
    )
    await message.answer(
        f"Пакет <b>{payment_data.name}</b> создан с услугами: {services_text}!",
        parse_mode="HTML",
        reply_markup=PaymentKeyboard.build(),
    )
    await session_with_commit.commit()
    await state.set_state(GeneralStates.payment_view)
