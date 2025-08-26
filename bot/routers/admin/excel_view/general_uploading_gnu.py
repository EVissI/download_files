from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup

from bot.common.filters.user_info import UserInfo
from bot.common.func.excel_generate import generate_detailed_analysis_report
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.markup.excel_view import ExcelKeyboard
from bot.common.texts import get_text
from bot.db.dao import DetailedAnalysisDAO

detailed_unloading_router = Router()

class DetailedAnalysisInputDate(StatesGroup):
    """
    Состояния для ввода диапазона дат в процессе выгрузки детального анализа.
    """
    Date = State()

class GeneralUnloadingCallback(CallbackData, prefix="general_unloading"):
    """
    Данные обратного вызова для действий выгрузки детального анализа.
    """
    action: str
    type: str

def get_general_unloading_kb(type: str) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для опций выгрузки детального анализа с предопределенными временными диапазонами.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Сегодня",
        callback_data=GeneralUnloadingCallback(action="today", type=type).pack(),
    )
    builder.button(
        text="Вчера",
        callback_data=GeneralUnloadingCallback(action="yesterday", type=type).pack(),
    )
    builder.button(
        text="Неделя",
        callback_data=GeneralUnloadingCallback(action="week", type=type).pack(),
    )
    builder.button(
        text="Месяц",
        callback_data=GeneralUnloadingCallback(action="month", type=type).pack(),
    )
    builder.button(
        text="Полгода",
        callback_data=GeneralUnloadingCallback(action="half_year", type=type).pack(),
    )
    builder.button(
        text="Всё время",
        callback_data=GeneralUnloadingCallback(action="all_time", type=type).pack(),
    )
    builder.button(
        text="Свой диапазон дат",
        callback_data=GeneralUnloadingCallback(action="custom", type=type).pack(),
    )
    builder.button(
        text="Отмена",
        callback_data=GeneralUnloadingCallback(action="back", type=type).pack()
    )
    builder.adjust(1)
    return builder.as_markup()

@detailed_unloading_router.message(
    F.text == ExcelKeyboard.get_kb_text()["general_unloading_gnu"],
    StateFilter(GeneralStates.excel_view),
)
async def handle_detailed_unloading(message: Message, state: FSMContext):
    """
    Показывает клавиатуру с опциями выгрузки детального анализа.
    """
    await message.answer(
        "Выберите временной диапазон для выгрузки детального анализа:",
        reply_markup=get_general_unloading_kb('gnu')
    )

@detailed_unloading_router.callback_query(GeneralUnloadingCallback.filter(F.type == "gnu"), UserInfo())
async def handle_detailed_unloading_callback(
    callback: CallbackQuery,
    callback_data: GeneralUnloadingCallback,
    state: FSMContext,
    session_without_commit: AsyncSession,
):
    await callback.message.delete()

    now = datetime.now()
    start_date = None
    end_date = None
    caption = None
    filename_suffix = None

    match callback_data.action:
        case "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = "Детальный анализ матчей за сегодня"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}"
        case "yesterday":
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = "Детальный анализ матчей за вчера"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}"
        case "week":
            start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = "Детальный анализ матчей за текущую неделю"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        case "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ матчей за {start_date.strftime('%m.%Y')}"
            filename_suffix = f"{start_date.strftime('%Y%m')}"
        case "half_year":
            start_date = (now - timedelta(days=182)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = "Детальный анализ матчей за последние полгода"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        case "all_time":
            start_date = None
            end_date = None
            caption = "Детальный анализ матчей за всё время"
            filename_suffix = f"{now.strftime('%Y%m%d')}"
        case "custom":
            await callback.message.answer(
                "Введите диапазон дат в формате ДД.ММ.ГГГГ-ДД.ММ.ГГГГ",
                reply_markup=get_cancel_kb(),
            )
            await state.set_state(DetailedAnalysisInputDate.Date)
            return
        case "back":
            await state.set_state(GeneralStates.excel_view)
            await callback.message.answer(
                "Вы вернулись в главное меню.",
                reply_markup=ExcelKeyboard.build()
            )
            return

    logger.info(f"Запрос детального анализа за период: {start_date} - {end_date}")

    dao = DetailedAnalysisDAO(session_without_commit)
    try:
        excel_buffer = await generate_detailed_analysis_report(
            dao, start_date=start_date, end_date=end_date
        )
        await callback.message.answer_document(
            document=BufferedInputFile(
                excel_buffer.getvalue(),
                filename=f"detailed_statistics_{filename_suffix}.xlsx",
            ),
            caption=caption,
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
    except Exception as e:
        logger.error(f"Ошибка при генерации отчета: {e}")
        await callback.message.answer("Ошибка при генерации отчета. Попробуйте позже.")
        await state.set_state(GeneralStates.excel_view)

@detailed_unloading_router.message(F.text == get_text("cancel"), StateFilter(DetailedAnalysisInputDate.Date), UserInfo())
async def cancel_detailed_unloading(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "Отмена",
        reply_markup=ExcelKeyboard.build(),
    )
    await state.set_state(GeneralStates.excel_view)

@detailed_unloading_router.message(F.text, StateFilter(DetailedAnalysisInputDate.Date), UserInfo())
async def handle_detailed_date_input(
    message: Message,
    state: FSMContext,
    session_without_commit: AsyncSession,
):
    """
    Обрабатывает ввод диапазона дат для выгрузки детального анализа.
    """
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

        logger.info(f"Запрос детального анализа с {start_date} по {end_date}")

        dao = DetailedAnalysisDAO(session_without_commit)
        excel_buffer = await generate_detailed_analysis_report(
            dao, start_date=start_date, end_date=end_date
        )

        await message.answer_document(
            document=BufferedInputFile(
                excel_buffer.getvalue(),
                filename=f"detailed_statistics_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.xlsx",
            ),
            caption=f"Детальный анализ матчей с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}",
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
    except ValueError as e:
        logger.error(f"Ошибка при обработке даты: {e}")
        await message.answer(
            "Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ-ДД.ММ.ГГГГ."
        )