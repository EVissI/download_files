from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from bot.common.filters.user_info import UserInfo
from bot.common.func.excel_generate import generate_detailed_user_analysis_report
from bot.common.general_states import GeneralStates
from bot.common.kbds.inline.paginate import PlayerNameCallback, get_player_names_kb
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.excel_view import ExcelKeyboard
from bot.common.texts import get_text
from bot.db.dao import DetailedAnalysisDAO
from bot.db.dao import DetailedAnalysisDAO, UserDAO
from bot.db.models import DetailedAnalysis

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key
from bot.config import translator_hub
if TYPE_CHECKING:
    from locales.stub import TranslatorRunner
detailed_user_unloading_router = Router()


class DetailedUserInputData(StatesGroup):
    """
    Состояния для ввода имени игрока и диапазона дат в процессе выгрузки детального анализа.
    """
    Date = State()


class DetailedUserUnloadingCallback(CallbackData, prefix="detailed_user_unloading"):
    """
    Данные обратного вызова для действий выгрузки детального анализа.
    """
    action: str


def get_detailed_user_unloading_kb() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для опций выгрузки детального анализа с предопределенными временными диапазонами.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Сегодня",
        callback_data=DetailedUserUnloadingCallback(action="today").pack(),
    )
    builder.button(
        text="Вчера",
        callback_data=DetailedUserUnloadingCallback(action="yesterday").pack(),
    )
    builder.button(
        text="Неделя",
        callback_data=DetailedUserUnloadingCallback(action="week").pack(),
    )
    builder.button(
        text="Месяц",
        callback_data=DetailedUserUnloadingCallback(action="month").pack(),
    )
    builder.button(
        text="Полгода",
        callback_data=DetailedUserUnloadingCallback(action="half_year").pack(),
    )
    builder.button(
        text="Всё время",
        callback_data=DetailedUserUnloadingCallback(action="all_time").pack(),
    )
    builder.button(
        text="Свой диапазон дат",
        callback_data=DetailedUserUnloadingCallback(action="custom").pack(),
    )
    builder.button(
        text="Отмена",
        callback_data=DetailedUserUnloadingCallback(action="back").pack()
    )
    builder.adjust(1)
    return builder.as_markup()


@detailed_user_unloading_router.message(
    F.text == ExcelKeyboard.get_kb_text()["upload_by_user_gnu"],
    StateFilter(GeneralStates.excel_view),
)
async def handle_detailed_user_unloading(
    message: Message,
    state: FSMContext,
    session_without_commit: AsyncSession,
):
    """
    Показывает клавиатуру с именами игроков для выгрузки детального анализа.
    """
    dao = DetailedAnalysisDAO(session_without_commit)
    player_names = await dao.get_all_unique_player_names()
    if not player_names:
        await message.answer("Нет доступных никнеймов игроков.")
        return
    await message.answer(
        "Выберите никнейм игрока для выгрузки детального анализа:",
        reply_markup=get_player_names_kb(player_names, page=0),
    )


@detailed_user_unloading_router.callback_query(
    PlayerNameCallback.filter()
)
async def handle_player_name_pagination(
    callback: CallbackQuery,
    callback_data: PlayerNameCallback,
    state: FSMContext,
    session_without_commit: AsyncSession,
):
    dao = DetailedAnalysisDAO(session_without_commit)
    player_names = await dao.get_all_unique_player_names()
    page = callback_data.page

    if callback_data.action == "select":
        await state.update_data(player_name=callback_data.player_name)
        await callback.message.edit_text(
            "Выберите временной диапазон для выгрузки детального анализа:",
            reply_markup=get_detailed_user_unloading_kb(),
        )
        await state.set_state(GeneralStates.excel_view)
    elif callback_data.action in ("prev", "next"):
        await callback.message.edit_reply_markup(
            reply_markup=get_player_names_kb(player_names, page=page)
        )


@detailed_user_unloading_router.message(
   F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")), StateFilter(DetailedUserInputData)
)
async def cancel_detailed_user_unloading(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "Отмена",
        reply_markup=ExcelKeyboard.build(),
    )
    await state.set_state(GeneralStates.excel_view)


@detailed_user_unloading_router.callback_query(
    DetailedUserUnloadingCallback.filter(), UserInfo()
)
async def handle_detailed_user_unloading_callback(
    callback: CallbackQuery,
    callback_data: DetailedUserUnloadingCallback,
    state: FSMContext,
    session_without_commit: AsyncSession,
    i18n
):
    await callback.message.delete()
    user_data = await state.get_data()
    player_name = user_data.get("player_name")

    if not player_name:
        await callback.message.answer(
            "Игровой никнейм не указан.",
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
        return

    now = datetime.now()
    start_date = None
    end_date = None
    caption = None
    filename_suffix = None

    match callback_data.action:
        case "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для {player_name} за сегодня"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}"
        case "yesterday":
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для {player_name} за вчера"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}"
        case "week":
            start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для {player_name} за текущую неделю"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        case "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для {player_name} за {start_date.strftime('%m.%Y')}"
            filename_suffix = f"{start_date.strftime('%Y%m')}"
        case "half_year":
            start_date = (now - timedelta(days=182)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для {player_name} за последние полгода"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        case "all_time":
            start_date = None
            end_date = None
            caption = f"Детальный анализ для {player_name} за всё время"
            filename_suffix = f"{now.strftime('%Y%m%d')}"
        case "custom":
            await callback.message.answer(
                "Введите диапазон дат в формате ДД.ММ.ГГГГ-ДД.ММ.ГГГГ",
                reply_markup=get_cancel_kb(i18n),
            )
            await state.set_state(DetailedUserInputData.Date)
            return
        case "back":
            dao = DetailedAnalysisDAO(session_without_commit)
            player_names = await dao.get_all_unique_player_names()
            if not player_names:
                await callback.message.answer("Нет доступных никнеймов игроков.")
                return
            await callback.message.answer(
                "Выберите никнейм игрока для выгрузки детального анализа:",
                reply_markup=get_player_names_kb(player_names, page=0),
            )
            await state.set_state(GeneralStates.excel_view)
            return

    logger.info(f"Запрос данных игрока {player_name} за период: {start_date} - {end_date}")

    dao = DetailedAnalysisDAO(session_without_commit)
    try:
        excel_buffer = await generate_detailed_user_analysis_report(
            dao, player_name=player_name, start_date=start_date, end_date=end_date
        )
        await callback.message.answer_document(
            document=BufferedInputFile(
                excel_buffer.getvalue(),
                filename=f"{player_name}_detailed_statistics_{filename_suffix}.xlsx",
            ),
            caption=caption,
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
    except ValueError as e:
        logger.error(f"Ошибка при генерации отчёта для {player_name}: {e}")
        await callback.message.answer(str(e))
        await state.set_state(GeneralStates.excel_view)


@detailed_user_unloading_router.message(F.text, StateFilter(DetailedUserInputData.Date))
async def handle_detailed_user_date_input(
    message: Message,
    state: FSMContext,
    session_without_commit: AsyncSession,
):
    user_data = await state.get_data()
    player_name = user_data.get("player_name")

    if not player_name:
        await message.answer(
            "Игровой никнейм не указан.",
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
        return

    try:
        start_date_str, end_date_str = message.text.split("-")
        start_date = datetime.strptime(start_date_str.strip(), "%d.%m.%Y").replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = datetime.strptime(end_date_str.strip(), "%d.%m.%Y").replace(
            hour=23, minute=59, second=59, microsecond=999999
        )

        if start_date > end_date:
            await message.answer("Начальная дата не может быть позже конечной даты.")
            return

        logger.info(f"Запрос данных игрока {player_name} с {start_date} по {end_date}")

        dao = DetailedAnalysisDAO(session_without_commit)
        excel_buffer = await generate_detailed_user_analysis_report(
            dao, player_name=player_name, start_date=start_date, end_date=end_date
        )

        await message.answer_document(
            document=BufferedInputFile(
                excel_buffer.getvalue(),
                filename=f"{player_name}_detailed_statistics_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.xlsx",
            ),
            caption=f"Детальный анализ для {player_name} с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}",
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
    except ValueError as e:
        logger.error(f"Ошибка при обработке даты: {e}")
        await message.answer(
            "Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ-ДД.ММ.ГГГГ."
        )
