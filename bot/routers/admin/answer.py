from io import BytesIO
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.kbds.inline.answer import (
    AnswerCallback,
    ResultCallback,
    get_player_keyboard,
    get_result_keyboard,
)
from bot.db.redis import redis_client
from bot.common.func.func import determine_rank, extract_eg_summary, format_value
from loguru import logger


class AnswerDialog(StatesGroup):
    photo = State()
    confirm = State()

answer_router = Router()

@answer_router.callback_query(AnswerCallback.filter())
async def handle_reply_callback(
    callback: CallbackQuery, callback_data: AnswerCallback, state: FSMContext
):
    user_id = callback_data.user_id
    analysis_id = callback_data.analysis_id

    admin_messages = await redis_client.get_admin_messages(user_id)

    for admin_id, message_id in admin_messages:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=admin_id, message_id=message_id, reply_markup=None
            )
        except Exception as e:
            logger.error(
                f"Не удалось удалить клавиатуру у сообщения {message_id} для админа {admin_id}: {e}"
            )

    await redis_client.clear_admin_messages(user_id)
    await state.set_state(AnswerDialog.photo)
    await state.update_data(user_id=user_id, analysis_id=analysis_id)
    await callback.message.answer("Отправьте изображение.")


@answer_router.message(StateFilter(AnswerDialog.photo), F.photo)
async def handle_photo(message: Message, state: FSMContext):
    try:
        waiting_manager = WaitingMessageManager(message.chat.id, message.bot)
        photo = message.photo[-1]
        await waiting_manager.start()

        photo_bytes = BytesIO()
        await message.bot.download(photo.file_id, destination=photo_bytes)

        summary = extract_eg_summary(photo_bytes.getvalue())
        rank_player1 = determine_rank(
            summary[list(summary.keys())[0]].get("quality", 0.0)
        )
        rank_player2 = determine_rank(
            summary[list(summary.keys())[1]].get("quality", 0.0)
        )

        await state.update_data(
            player1=list(summary.keys())[0], player2=list(summary.keys())[1]
        )
        data = await state.get_data()
        user_id = data.get("user_id")
        analysis_id = data.get("analysis_id")

        # Получаем существующие данные из Redis
        redis_key = f"analysis:{user_id}:{analysis_id}"
        existing_data = await redis_client.get(redis_key)
        if existing_data:
            existing_data = json.loads(existing_data)
            existing_data["summary"] = summary
            await redis_client.set(redis_key, json.dumps(existing_data))
        else:
            logger.error(f"Данные анализа не найдены в Redis: {redis_key}")
            return


        formatted_result = (
            f"<b>Результат анализа:</b>\n\n"
            f"<b>Игрок 1:</b> {list(summary.keys())[0]}\n"
            f"Ошибки: {summary[list(summary.keys())[0]].get('error', 'нет')} "
            f"({summary[list(summary.keys())[0]].get('errors_extra', 'нет')})\n"
            f"Ошибки удвоений: {summary[list(summary.keys())[0]].get('doubling', 'нет')} "
            f"({summary[list(summary.keys())[0]].get('doubling_extra', 'нет')})\n"
            f"Ошибки взятий: {summary[list(summary.keys())[0]].get('taking', 'нет')}\n"
            f"Удача: {format_value(summary[list(summary.keys())[0]].get('luck', 'нет'), True)} "
            f"({summary[list(summary.keys())[0]].get('luck_extra', 'нет')})\n"
            f"Качество игры (PR): {format_value(summary[list(summary.keys())[0]].get('quality', 'нет'), True)}\n"
            f"<b>Ранг:</b> {rank_player1}\n\n"
            f"<b>Игрок 2:</b> {list(summary.keys())[1]}\n"
            f"Ошибки: {summary[list(summary.keys())[1]].get('errors', 'нет')} "
            f"({summary[list(summary.keys())[1]].get('errors_extra', 'нет')})\n"
            f"Ошибки удвоений: {summary[list(summary.keys())[1]].get('doubling', 'нет')} "
            f"({summary[list(summary.keys())[1]].get('doubling_extra', 'нет')})\n"
            f"Ошибки взятий: {summary[list(summary.keys())[1]].get('taking', 'нет')}\n"
            f"Удача: {format_value(summary[list(summary.keys())[1]].get('luck', 'нет'), True)} "
            f"({summary[list(summary.keys())[1]].get('luck_extra', 'нет')})\n"
            f"Качество игры (PR): {format_value(summary[list(summary.keys())[1]].get('quality', 'нет'), True)}\n"
            f"<b>Ранг:</b> {rank_player2}\n"
        )

        await message.answer(
            formatted_result, parse_mode="HTML", reply_markup=get_result_keyboard()
        )

        await waiting_manager.stop()
    except Exception as e:
        logger.error(f"Ошибка при обработке фото: {e}")
        await message.answer("Произошла ошибка при обработке фото.")


@answer_router.callback_query(ResultCallback.filter(F.action == "send_to_user"))
async def handle_send_to_user(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        data = await state.get_data()
        user_id = data.get("user_id")
        analysis_id = data.get("analysis_id")
        player1 = data.get("player1")
        player2 = data.get("player2")

        await callback.bot.send_message(
            chat_id=user_id,
            text=callback.message.text + "\n\nКто вы из игроков?",
            reply_markup=get_player_keyboard(player1, player2, analysis_id),
        )
        await callback.answer("Сообщение отправлено пользователю.")
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка при отправке пользователю: {e}")
        await callback.message.answer("Произошла ошибка при отправке.")


@answer_router.callback_query(ResultCallback.filter(F.action == "try_again"))
async def handle_try_again(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(AnswerDialog.photo)
    await callback.message.answer("Попробуйте снова. Отправьте изображение.")


@answer_router.message(StateFilter(AnswerDialog.photo), ~F.photo)
async def handle_non_photo(message: Message):
    await message.answer("Пожалуйста, отправьте изображение.")
