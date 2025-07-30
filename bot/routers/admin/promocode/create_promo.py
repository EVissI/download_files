from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from sqlalchemy.exc import IntegrityError
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.promo_code import PromoKeyboard
from bot.db.dao import PromoCodeDAO
from bot.db.models import Promocode
from bot.db.schemas import SPromocode

from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


promo_create_router = Router()


class PromoCreateStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_count = State()
    waiting_for_max_usage = State()
    waiting_for_duration = State()  # новое состояние


@promo_create_router.message(
    F.text == PromoKeyboard.get_kb_text()["create_promo"],
    StateFilter(GeneralStates.promo_view),
)
async def start_create_promo(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.set_state(PromoCreateStates.waiting_for_code)
    await message.answer(
        "Введите название промокода(например: Happy2025):",
        reply_markup=get_cancel_kb(i18n),
    )


@promo_create_router.message(
    F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
    StateFilter(PromoCreateStates),
)
async def cancel_create_promo(
    message: Message, state: FSMContext, i18n: TranslatorRunner
):
    await state.set_state(GeneralStates.promo_view)
    await message.answer(
        "Создание промокода отменено.",
        reply_markup=PromoKeyboard.build(),
        parse_mode="HTML",
    )


@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_code))
async def get_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await state.set_state(PromoCreateStates.waiting_for_count)
    await message.answer(
        "Введите кол-во анлиза игр доступных по промокоду(0 для неограниченного кол-ва):"
    )


@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_count))
async def get_days(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введите число (целое число):")
        return
    await state.update_data(analiz_count=int(message.text))
    await state.set_state(PromoCreateStates.waiting_for_max_usage)
    await message.answer(
        "Введите максимальное количество использований (или 0 для неограниченного):"
    )


@promo_create_router.message(StateFilter(PromoCreateStates.waiting_for_max_usage))
async def get_max_usage(message: Message, state: FSMContext, session_without_commit):
    if not message.text.isdigit():
        await message.answer("Введите число использований (целое число):")
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
    analiz_count = data["analiz_count"]
    max_usage = data["max_usage"]
    promocode = SPromocode(
        code=code,
        analiz_count=analiz_count if analiz_count > 0 else None,
        is_active=True,
        max_usage=max_usage if max_usage > 0 else None,
        activate_count=0,
        duration_days=duration_days if duration_days > 0 else None,
    )
    dao = PromoCodeDAO(session_without_commit)
    await dao.add(promocode)
    await session_without_commit.commit()
    await message.answer(
        f"Промокод <b>{code}</b> создан!",
        parse_mode="HTML",
        reply_markup=PromoKeyboard.build(),
    )
    await state.set_state(GeneralStates.promo_view)
