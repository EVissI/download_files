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
from bot.db.dao import DetailedAnalysisDAO, UserDAO
from bot.db.models import DetailedAnalysis

from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner
from bot.common.utils.i18n import get_all_locales_for_key

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner

detailed_user_unloading_router = Router()


class DetailedUserInputData(StatesGroup):
    """
    States for inputting player username and date range in the detailed user unloading process.
    """
    Date = State()


class DetailedUserUnloadingCallback(CallbackData, prefix="detailed_user_unloading"):
    """
    Callback data for detailed user unloading actions.
    """

    action: str


def get_detailed_user_unloading_kb() -> InlineKeyboardMarkup:
    """
    Creates an inline keyboard for detailed user unloading options.
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Выгрузка за все время",
        callback_data=DetailedUserUnloadingCallback(
            action="detailed_user_unloading"
        ).pack(),
    )
    builder.button(
        text="Выгрузка за месяц",
        callback_data=DetailedUserUnloadingCallback(action="uploading_by_month").pack(),
    )
    builder.button(
        text="Выгрузка по дате",
        callback_data=DetailedUserUnloadingCallback(action="uploading_by_date").pack(),
    )
    builder.button(
        text="Отмена", callback_data=DetailedUserUnloadingCallback(action="back").pack()
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
    i18n: TranslatorRunner,
    session_without_commit: AsyncSession,
):
    """
    Показываем клавиатуру с никнеймами игроков для выгрузки детального анализа.
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
            "Выберите действие для выгрузки детального анализа",
            reply_markup=get_detailed_user_unloading_kb(),
        )
        await state.set_state(GeneralStates.excel_view)
    elif callback_data.action in ("prev", "next"):
        await callback.message.edit_reply_markup(
            reply_markup=get_player_names_kb(player_names, page=page)
        )


@detailed_user_unloading_router.message(
    F.text == get_text("cancel"), StateFilter(DetailedUserInputData)
)
async def cancel_detailed_user_unloading(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        message.text,
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
    i18n: TranslatorRunner,
):
    await callback.message.delete()
    user_data = await state.get_data()
    player_name = user_data.get("player_name")

    if not player_name:
        await callback.message.answer(
            "Игровой юзернейм не указан",
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
        return

    match callback_data.action:
        case "uploading_by_date":
            await callback.message.answer(
                "Введите дату в формате DD.MM.YYYY-DD.MM.YYYY для выгрузки данных",
                reply_markup=get_cancel_kb(i18n),
            )
            await state.set_state(DetailedUserInputData.Date)
        case "uploading_by_month":
            # Выгрузка за текущий месяц
            now = datetime.now()
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_date = start_date.replace(year=now.year + 1, month=1) - timedelta(microseconds=1)
            else:
                end_date = start_date.replace(month=now.month + 1) - timedelta(microseconds=1)

            logger.info(f"Запрос данных игрока {player_name} за текущий месяц: {start_date} - {end_date}")

            dao = DetailedAnalysisDAO(session_without_commit)
            try:
                excel_buffer = await generate_detailed_user_analysis_report(
                    dao, player_name=player_name, start_date=start_date, end_date=end_date
                )
                await callback.message.answer_document(
                    document=BufferedInputFile(
                        excel_buffer.getvalue(),
                        filename=f"{player_name}_detailed_statistics_{start_date.strftime('%Y%m')}.xlsx",
                    ),
                    caption=f"Детальный анализ игрока за {start_date.strftime('%m.%Y')}",
                    reply_markup=ExcelKeyboard.build(),
                )
                await state.set_state(GeneralStates.excel_view)
            except ValueError as e:
                logger.error(f"Ошибка при генерации отчёта для {player_name}: {e}")
                await callback.message.answer(str(e))
            await state.set_state(GeneralStates.excel_view)
        case "detailed_user_unloading":
            dao = DetailedAnalysisDAO(session_without_commit)
            try:
                excel_buffer = await generate_detailed_user_analysis_report(
                    dao, player_name=player_name
                )
                await callback.message.answer_document(
                    document=BufferedInputFile(
                        excel_buffer.getvalue(),
                        filename=f"{player_name}_detailed_statistics_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    ),
                    caption="Детальный анализ за все время",
                    reply_markup=ExcelKeyboard.build(),
                )
                await state.set_state(GeneralStates.excel_view)
            except ValueError as e:
                logger.error(f"Ошибка при генерации отчёта для {player_name}: {e}")
                await callback.message.answer(str(e))
            await state.set_state(GeneralStates.excel_view)
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
            "Игровой юзернейм не указан",
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
            caption=f"Детальный анализ игрока за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
            reply_markup=ExcelKeyboard.build(),
        )
        await state.set_state(GeneralStates.excel_view)
    except ValueError as e:
        logger.error(f"Ошибка при обработке даты: {e}")
        await message.answer(
            "Неверный формат даты. Пожалуйста, используйте формат DD.MM.YYYY-DD.MM.YYYY."
        )
