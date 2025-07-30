# from datetime import datetime
# from aiogram import Router, F
# from aiogram.types import Message, CallbackQuery, BufferedInputFile
# from aiogram.filters import StateFilter
# from aiogram.fsm.context import FSMContext
# from loguru import logger
# from sqlalchemy.ext.asyncio import AsyncSession
# from aiogram.fsm.state import State, StatesGroup

# from bot.common.filters.user_info import UserInfo
# from bot.common.func.excel_generate import generate_users_analysis_report
# from bot.common.general_states import GeneralStates
# from bot.common.kbds.inline.excel import (
#     GeneralUnloadingCallback,
#     get_general_unloading_kb,
# )
# from bot.common.kbds.markup.cancel import get_cancel_kb
# from bot.common.kbds.markup.excel_view import ExcelKeyboard
# from bot.common.kbds.markup.main_kb import MainKeyboard
# from bot.db.dao import UserDAO
# from bot.db.models import User

# general_unloading_router = Router()


# class InputDate(StatesGroup):
#     """
#     State for inputting a date in the general unloading process.
#     """
#     Date = State()


# @general_unloading_router.message(
#     F.text == ExcelKeyboard.get_kb_text()["general_unloading_ex"],
#     StateFilter(GeneralStates.excel_view),
# )
# async def handle_general_unloading(message: Message, state: FSMContext):
#     """
#     Handles the general unloading command in the Excel view state.
#     """
#     await message.answer(message.text, reply_markup=get_general_unloading_kb('ex'))


# @general_unloading_router.callback_query(GeneralUnloadingCallback.filter(F.type == "ex"))
# async def handle_general_unloading_callback(
#     callback: CallbackQuery,
#     callback_data: GeneralUnloadingCallback,
#     state: FSMContext,
#     session_without_commit: AsyncSession,
# ):
#     await callback.message.delete()
#     match callback_data.action:
#         case "uploading_by_date":
#             await callback.message.answer(
#                 "Введите дату в формате DD.MM.YYYY-DD.MM.YYYY для выгрузки данных по пользователям",
#                 reply_markup=get_cancel_kb(),
#             )
#             await state.set_state(InputDate.Date)
#         case "general_unloading":
#             dao = UserDAO(session_without_commit)
#             excel_buffer = await generate_users_analysis_report(dao)
#             await callback.message.answer_document(
#                 document=BufferedInputFile(
#                     excel_buffer.getvalue(),
#                     filename=f"statistics_{datetime.now().strftime('%Y%m%d')}.xlsx",
#                 ),
#                 caption="Статистика игроков за последний месяц",
#                 reply_markup=ExcelKeyboard.build(),
#             )
#             await state.set_state(GeneralStates.excel_view)
#         case "back":
#             await state.set_state(GeneralStates.excel_view)
#             await callback.message.answer(
#                 "Вы вернулись в главное меню.", reply_markup=ExcelKeyboard.build()
#             )


# @general_unloading_router.message(F.text, StateFilter(InputDate.Date), UserInfo())
# async def handle_date_input(
#     message: Message,
#     state: FSMContext,
#     session_without_commit: AsyncSession,
#     user_info: User,
# ):
#     """
#     Handles the input of a date range for user data unloading.
#     """
#     try:
#         start_date_str, end_date_str = message.text.split("-")
#         start_date = datetime.strptime(start_date_str.strip(), "%d.%m.%Y").replace(
#             hour=0, minute=0, second=0, microsecond=0
#         )
#         end_date = datetime.strptime(end_date_str.strip(), "%d.%m.%Y").replace(
#             hour=23, minute=59, second=59, microsecond=999999
#         )

#         if start_date > end_date:
#             await message.answer("Начальная дата не может быть позже конечной даты.")
#             return

#         # Добавим логирование для проверки дат
#         logger.info(f"Запрос данных с {start_date} по {end_date}")

#         dao = UserDAO(session_without_commit)
#         excel_buffer = await generate_users_analysis_report(dao, start_date, end_date)

#         await message.answer_document(
#             document=BufferedInputFile(
#                 excel_buffer.getvalue(),
#                 filename=f"statistics_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.xlsx",
#             ),
#             caption="Статистика игроков за указанный период",
#             reply_markup=ExcelKeyboard.build(),
#         )
#         await state.set_state(GeneralStates.excel_view)
#     except ValueError as e:
#         logger.error(f"Ошибка при обработке даты: {e}")
#         await message.answer(
#             "Неверный формат даты. Пожалуйста, используйте формат DD.MM.YYYY-DD.MM.YYYY."
#         )
