# from datetime import datetime
# from aiogram import Router, F
# from aiogram.types import Message, CallbackQuery, BufferedInputFile
# from aiogram.filters import StateFilter, Command
# from aiogram.fsm.context import FSMContext
# from loguru import logger
# from sqlalchemy.ext.asyncio import AsyncSession
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.utils.keyboard import InlineKeyboardBuilder
# from aiogram.filters.callback_data import CallbackData
# from aiogram.types import InlineKeyboardMarkup

# from bot.common.filters.user_info import UserInfo
# from bot.common.func.excel_generate import generate_user_analysis_report
# from bot.common.general_states import GeneralStates
# from bot.common.kbds.markup.cancel import get_cancel_kb
# from bot.common.kbds.markup.excel_view import ExcelKeyboard
# from bot.common.texts import get_text
# from bot.db.dao import UserDAO
# from bot.db.models import User

# user_unloading_router = Router()


# class InputUserData(StatesGroup):
#     """
#     States for inputting user ID and date range in the user unloading process.
#     """
#     UserID = State()
#     Date = State()


# class UserUnloadingCallback(CallbackData, prefix="user_unloading"):
#     """
#     Callback data for user unloading actions.
#     """
#     action: str


# def get_user_unloading_kb() -> InlineKeyboardMarkup:
#     """
#     Creates an inline keyboard for user unloading options.
#     """
#     builder = InlineKeyboardBuilder()
#     builder.button(
#         text="Выгрузка за месяц",
#         callback_data=UserUnloadingCallback(action="user_unloading").pack()
#     )
#     builder.button(
#         text="Выгрузка по дате",
#         callback_data=UserUnloadingCallback(action="uploading_by_date").pack()
#     )
#     builder.button(
#         text="Отмена",
#         callback_data=UserUnloadingCallback(action="back").pack()
#     )
#     builder.adjust(1)
#     return builder.as_markup()


# @user_unloading_router.message(
#     F.text == ExcelKeyboard.get_kb_text()["upload_by_user_ex"],
#     StateFilter(GeneralStates.excel_view),
# )
# async def handle_user_unloading(message: Message, state: FSMContext):
#     """
#     Handles the user unloading command in the Excel view state.
#     Initiates the process by asking for user ID.
#     """
#     await message.answer(
#         "Введите ID пользователя для выгрузки статистики",
#         reply_markup=get_cancel_kb(),
#     )
#     await state.set_state(InputUserData.UserID)

# @user_unloading_router.message(F.text == get_text("cancel"), StateFilter(InputUserData))
# async def cancel_detailed_user_unloading(
#     message: Message,
#     state: FSMContext,
# ):
#     """
#     Cancels the detailed user unloading process and returns to the Excel view state.
#     """
#     await state.clear()
#     await message.answer(
#         message.text,
#         reply_markup=ExcelKeyboard.build(),
#     )
#     await state.set_state(GeneralStates.excel_view)

# @user_unloading_router.message(F.text, StateFilter(InputUserData.UserID))
# async def handle_user_id_input(
#     message: Message,
#     state: FSMContext,
# ):
#     """
#     Handles the input of a user ID for data unloading.
#     """
#     try:
#         user_id = int(message.text.strip())
#         await state.update_data(user_id=user_id)
#         await message.answer(
#             "Выберите действие для выгрузки статистики",
#             reply_markup=get_user_unloading_kb(),
#         )
#         await state.set_state(GeneralStates.excel_view)
#     except ValueError as e:
#         logger.error(f"Ошибка при обработке ID пользователя: {e}")
#         await message.answer(
#             "Неверный формат ID пользователя. Пожалуйста, введите целое число."
#         )


# @user_unloading_router.callback_query(UserUnloadingCallback.filter(), UserInfo())
# async def handle_user_unloading_callback(
#     callback: CallbackQuery,
#     callback_data: UserUnloadingCallback,
#     state: FSMContext,
#     session_without_commit: AsyncSession,
#     user_info: User,
# ):
#     """
#     Handles callback queries for user unloading actions.
#     """
#     await callback.message.delete()
#     user_data = await state.get_data()
#     user_id = user_data.get("user_id")

#     if not user_id:
#         await callback.message.answer(
#             "ID пользователя не указан. Введите /user_stats и укажите ID.",
#             reply_markup=ExcelKeyboard.build(),
#         )
#         await state.set_state(GeneralStates.excel_view)
#         return

#     match callback_data.action:
#         case "uploading_by_date":
#             await callback.message.answer(
#                 "Введите дату в формате DD.MM.YYYY-DD.MM.YYYY для выгрузки данных",
#                 reply_markup=get_cancel_kb(),
#             )
#             await state.set_state(InputUserData.Date)
#         case "user_unloading":
#             dao = UserDAO(session_without_commit)
#             try:
#                 excel_buffer = await generate_user_analysis_report(dao, user_id=user_id)
#                 await callback.message.answer_document(
#                     document=BufferedInputFile(
#                         excel_buffer.getvalue(),
#                         filename=f"user_{user_id}_statistics_{datetime.now().strftime('%Y%m%d')}.xlsx",
#                     ),
#                     caption="Статистика за последний месяц",
#                 )
#             except ValueError as e:
#                 logger.error(f"Ошибка при генерации отчёта для пользователя {user_id}: {e}")
#                 await callback.message.answer(str(e))
#             await state.set_state(GeneralStates.excel_view)
#         case "back":
#             await state.set_state(GeneralStates.excel_view)
#             await callback.message.answer(
#                 "Вы вернулись в главное меню.", reply_markup=ExcelKeyboard.build()
#             )


# @user_unloading_router.message(F.text, StateFilter(InputUserData.Date))
# async def handle_user_date_input(
#     message: Message,
#     state: FSMContext,
#     session_without_commit: AsyncSession,
# ):
#     """
#     Handles the input of a date range for user data unloading.
#     """
#     user_data = await state.get_data()
#     user_id = user_data.get("user_id")

#     if not user_id:
#         await message.answer(
#             "ID пользователя не указан. Введите /user_stats и укажите ID.",
#             reply_markup=ExcelKeyboard.build(),
#         )
#         await state.set_state(GeneralStates.excel_view)
#         return

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

#         logger.info(f"Запрос данных пользователя {user_id} с {start_date} по {end_date}")

#         dao = UserDAO(session_without_commit)
#         excel_buffer = await generate_user_analysis_report(
#             dao, user_id=user_id, start_date=start_date, end_date=end_date
#         )

#         await message.answer_document(
#             document=BufferedInputFile(
#                 excel_buffer.getvalue(),
#                 filename=f"user_{user_id}_statistics_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.xlsx",
#             ),
#             caption=f"Статистика пользователя за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
#             reply_markup=ExcelKeyboard.build(),
#         )
#         await state.set_state(GeneralStates.excel_view)
#     except ValueError as e:
#         logger.error(f"Ошибка при обработке даты: {e}")
#         await message.answer(
#             "Неверный формат даты. Пожалуйста, используйте формат DD.MM.YYYY-DD.MM.YYYY."
#         )