from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from loguru import logger
from sqlalchemy.exc import IntegrityError
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO, PromocodeServiceQuantityDAO
from bot.db.models import Promocode, PromocodeServiceQuantity, ServiceType
from bot.db.schemas import SPromocode, SPromocodeServiceQuantity

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


promo_create_router = Router()


class PromoCreateStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_service_type = State()
    waiting_for_service_quantity = State()
    waiting_for_add_more_services = State()
    waiting_for_max_usage = State()
    waiting_for_duration = State()


@promo_create_router.message(
    F.text == PromoKeyboard.get_kb_text()["create_promo"],
    StateFilter(GeneralStates.promo_view),
)
async def start_create_promo(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.set_state(PromoCreateStates.waiting_for_code)
    await message.answer(
        "Введите название промокода (например: Happy2025):",
        reply_markup=get_cancel_kb(i18n),
    )


@promo_create_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
    StateFilter(PromoCreateStates),
)
async def cancel_create_promo(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.clear()
    await state.set_state(GeneralStates.promo_view)
    await message.answer(
        "Создание промокода отменено.",
        reply_markup=PromoKeyboard.build(),
        parse_mode="HTML",
    )


@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_code))
async def get_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await state.set_state(PromoCreateStates.waiting_for_service_type)

    # Генерация инлайн-кнопок для выбора типа услуги
    data = await state.get_data()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=service_type.value,
                    callback_data=f"service_type:{service_type.name}",
                )
            ]
            for service_type in ServiceType
        ]
    )

    await message.answer(
        "Выберите тип сервиса для промокода:",
        reply_markup=keyboard,
    )


@promo_create_router.callback_query(
    StateFilter(PromoCreateStates.waiting_for_service_type),
    F.data.startswith("service_type:"),
)
async def select_service_type(callback: CallbackQuery, state: FSMContext):
    service_type_name = callback.data.split(":")[1]  # Получаем имя (например, ANALYSIS)
    service_type = ServiceType[
        service_type_name
    ]  # Преобразуем в перечисление

    await callback.message.delete()
    data = await state.get_data()
    services = data.get("services", [])
    services.append(
        {"service_type": service_type.name, "quantity": 0}
    )  # Сохраняем русское значение
    await state.update_data(services=services)

    await state.set_state(PromoCreateStates.waiting_for_service_quantity)
    await callback.message.answer(
        f"Введите число игр для <b>{service_type.value}</b>:"
    )
    await callback.answer()


@promo_create_router.message(
    StateFilter(PromoCreateStates.waiting_for_service_quantity)
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
        for service_type in ServiceType
        if service_type.name not in existing_services
    ]
    logger.info(f"Remaining services: {remaining_services}")
    if not remaining_services:  # Если все типы уже добавлены
        await state.set_state(PromoCreateStates.waiting_for_max_usage)
        await message.answer(
            "Все сервисы уже добавлены. Введите максимальное количество использований промокода (или 0 для неограниченного):"
        )
        return

    await state.set_state(PromoCreateStates.waiting_for_add_more_services)

    # Генерация кнопок "да/нет"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="add_more_services:yes"),
                InlineKeyboardButton(text="Нет", callback_data="add_more_services:no"),
            ]
        ]
    )

    await message.answer("Хотите добавить ещё один сервис?", reply_markup=keyboard)


@promo_create_router.callback_query(
    StateFilter(PromoCreateStates.waiting_for_add_more_services),
    F.data.startswith("add_more_services:"),
)
async def add_more_services(callback: CallbackQuery, state: FSMContext):
    choice = callback.data.split(":")[1]
    await callback.message.delete()

    if choice == "yes":
        await state.set_state(PromoCreateStates.waiting_for_service_type)

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
                for service_type in ServiceType
                if service_type.name
                not in existing_services  # Исключаем уже добавленные типы
            ]
        )

        await callback.message.answer(
            "Выберите тип следующей сервиса:",
            reply_markup=keyboard,
        )
    else:
        await state.set_state(PromoCreateStates.waiting_for_max_usage)
        await callback.message.answer(
            "Введите максимальное количество использований промокода (или 0 для неограниченного):"
        )


@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_max_usage))
async def get_max_usage(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число (целое число):")
        return

    max_usage = int(message.text)
    await state.update_data(max_usage=max_usage)
    await state.set_state(PromoCreateStates.waiting_for_duration)
    await message.answer("Введите срок действия промокода в днях (0 — бессрочно):")


@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_duration))
async def get_duration_days(
    message: Message, state: FSMContext, session_without_commit
):
    if not message.text.isdigit():
        await message.answer("Введите срок действия (целое число):")
        return

    duration_days = int(message.text)
    data = await state.get_data()
    code = data["code"]
    services = data["services"]
    max_usage = data["max_usage"]


    # Создание объекта SPromocode
    promo_data = SPromocode(
        code=code,
        is_active=True,
        max_usage=max_usage if max_usage > 0 else None,
        activate_count=0,
        duration_days=duration_days if duration_days > 0 else None,
    )

    # Сохранение в базе данных
    promo_dao = PromoCodeDAO(session_without_commit)
    service_dao = PromocodeServiceQuantityDAO(session_without_commit)
    promo = await promo_dao.add(promo_data)
    service_objects = [
        SPromocodeServiceQuantity(
            promocode_id=promo.id,
            service_type=service["service_type"],
            quantity=service["quantity"] if service["quantity"] > 0 else None,
        )
        for service in services
    ]
    services_objects:list[PromocodeServiceQuantity] = []
    for service in service_objects:
        services_objects.append(await service_dao.add(service))

    services_text = ", ".join(
        [
            f"{ServiceType[service.service_type].value} ({service.quantity})"
            for service in services_objects
        ]
    )
    await message.answer(
        f"Промокод <b>{promo_data.code}</b> создан с сервисами: {services_text}!",
        parse_mode="HTML",
        reply_markup=PromoKeyboard.build(),
    )
    await session_without_commit.commit()
    await state.clear()
    await state.set_state(GeneralStates.promo_view)
