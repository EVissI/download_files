from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.inline.user_settings import UserSettingsCallback
from bot.routers.admin.excel_view.upload_by_user_gnu import (
    DetailedUserUnloadingCallback,
    get_detailed_user_unloading_kb,
)
from bot.common.func.excel_generate import generate_detailed_user_analysis_report
from bot.db.dao import DetailedAnalysisDAO, UserDAO
from bot.config import translator_hub
from bot.common.utils.i18n import get_all_locales_for_key

user_settings_excel_router = Router()

class ExportUserState(StatesGroup):
    date_range = State()

@user_settings_excel_router.callback_query(UserSettingsCallback.filter(F.action == "export_excel"))
async def handle_export_from_user_settings(
    callback: CallbackQuery,
    callback_data: UserSettingsCallback,
    state: FSMContext,
):
    """
    Обработчик нажатия "Экспорт анализа" в user settings.
    Ожидается, что callback_data содержит поле с id пользователя (user_id или item_id).
    Сохраняем user_id в state и показываем клавиатуру с диапазонами.
    """
    await callback.message.delete()
    # поддерживаем разные названия поля
    user_id = callback_data.user_id

    await state.update_data(export_user_id=int(user_id))
    await callback.message.answer(
        "Выберите временной диапазон для выгрузки детального анализа:",
        reply_markup=get_detailed_user_unloading_kb(context='by_user_tg'),
    )
    await state.set_state(GeneralStates.excel_view)


@user_settings_excel_router.callback_query(DetailedUserUnloadingCallback.filter(F.context == "by_user_tg"))
async def handle_export_user_ranges(
    callback: CallbackQuery,
    callback_data: DetailedUserUnloadingCallback,
    state: FSMContext,
    session_without_commit: AsyncSession,
    i18n
):
    """
    Обработка выбора диапазона (today, week, month, custom и т.д.) и генерация файла для user_id из state.
    """
    await callback.message.delete()
    data = await state.get_data()
    user_id = data.get("export_user_id")

    now = datetime.now()
    start_date = None
    end_date = None
    caption = None
    filename_suffix = None

    action = callback_data.action
    match action:
        case "today":
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для пользователя {user_id} за сегодня"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}"
        case "yesterday":
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = (now - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для пользователя {user_id} за вчера"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}"
        case "week":
            start_date = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для пользователя {user_id} за текущую неделю"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        case "month":
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для пользователя {user_id} за {start_date.strftime('%m.%Y')}"
            filename_suffix = f"{start_date.strftime('%Y%m')}"
        case "half_year":
            start_date = (now - timedelta(days=182)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            caption = f"Детальный анализ для пользователя {user_id} за последние полгода"
            filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        case "all_time":
            start_date = None
            end_date = None
            caption = f"Детальный анализ для пользователя {user_id} за всё время"
            filename_suffix = f"{now.strftime('%Y%m%d')}"
        case "custom":
            await callback.message.answer(
                "Введите диапазон дат в формате ДД.ММ.ГГГГ - ДД.ММ.ГГГГ",
                reply_markup=get_cancel_kb(i18n))
            await state.set_state(ExportUserState.date_range)
        case "back":
            await callback.message.answer("Отмена", reply_markup=None)
            await state.clear()
            await state.set_state(GeneralStates.admin_panel)
            return

    # Получаем display name пользователя для подписи/имени файла если доступно
    user = await UserDAO(session_without_commit).find_one_or_none_by_id(user_id)
    display = user.admin_insert_name or user.username or str(user.id) if user else str(user_id)
    filename = f"user_{display}_detailed_statistics_{filename_suffix}.xlsx"

    dao = DetailedAnalysisDAO(session_without_commit)
    try:
        excel_buffer = await generate_detailed_user_analysis_report(dao, user_id=user_id, start_date=start_date, end_date=end_date)
        await callback.message.answer_document(
            document=BufferedInputFile(excel_buffer.getvalue(), filename=filename),
            caption=caption,
            reply_markup=AdminKeyboard.build(),
        )
        await state.set_state(GeneralStates.admin_panel)
        await state.clear()
    except ValueError as e:
        logger.error(f"Ошибка при генерации отчёта для user_id={user_id}: {e}")
        await callback.message.answer(str(e))
        await state.set_state(GeneralStates.admin_panel)
    except Exception as e:
        logger.exception(f"Unexpected error exporting detailed analysis for user_id={user_id}: {e}")
        await callback.message.answer("Ошибка при генерации отчёта.")
        await state.set_state(GeneralStates.admin_panel)


@user_settings_excel_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "auto-batch-stop")),
                StateFilter(ExportUserState.date_range))
async def cancel_export_user(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        message.text,
        reply_markup=AdminKeyboard.build()
    )

@user_settings_excel_router.message(StateFilter(ExportUserState.date_range), F.text)
async def handle_custom_date_range_input(
    message: Message,
    state: FSMContext,
    session_without_commit: AsyncSession,
):
    """
    Обработка пользовательского ввода диапазона дат в формате "ДД.ММ.ГГГГ - ДД.ММ.ГГГГ".
    """
    data = await state.get_data()
    user_id = data.get("export_user_id")

    date_text = message.text.strip()
    try:
        parts = [part.strip() for part in date_text.split("-")]
        if len(parts) != 2:
            raise ValueError("Неверный формат. Используйте: ДД.ММ.ГГГГ - ДД.ММ.ГГГГ")

        start_date = datetime.strptime(parts[0], "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = datetime.strptime(parts[1], "%d.%m.%Y").replace(hour=23, minute=59, second=59, microsecond=999999)

        if start_date > end_date:
            raise ValueError("Дата начала не может быть позже даты окончания.")

        # Получаем display name пользователя для подписи/имени файла если доступно
        user = await UserDAO(session_without_commit).find_one_or_none_by_id(user_id)
        display = user.admin_insert_name or user.username or str(user.id) if user else str(user_id)
        filename_suffix = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}"
        filename = f"user_{display}_detailed_statistics_{filename_suffix}.xlsx"
        caption = f"Детальный анализ для пользователя {user_id} с {start_date.strftime('%d.%m.%Y')} по {end_date.strftime('%d.%m.%Y')}"

        dao = DetailedAnalysisDAO(session_without_commit)
        excel_buffer = await generate_detailed_user_analysis_report(dao, user_id=user_id, start_date=start_date, end_date=end_date)
        await message.answer_document(
            document=BufferedInputFile(excel_buffer.getvalue(), filename=filename),
            caption=caption,
            reply_markup=AdminKeyboard.build(),
        )
        await state.set_state(GeneralStates.admin_panel)
        await state.clear()
    except ValueError as e:
        await message.answer(f"Ошибка: {e}\nПопробуйте снова или введите 'Отмена' для выхода.")