from zoneinfo import ZoneInfo
from aiogram import Router, F
from apscheduler.triggers.cron import CronTrigger
from bot.config import scheduler
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from bot.common.general_states import GeneralStates
from bot.common.kbds.markup.cancel import get_cancel_kb
from bot.common.kbds.inline.confirm import get_confrim_kb, ConfrimCallback
from bot.common.kbds.inline.paginate import get_paginated_checkbox_keyboard, PaginatedCheckboxCallback
from bot.common.kbds.markup.admin_panel import AdminKeyboard
from bot.common.tasks.gift import check_and_notify_gift
from bot.db.dao import MessageForNewDAO
from loguru import logger
from bot.config import translator_hub
from bot.common.utils.i18n import get_all_locales_for_key

message_for_new_router = Router()

class UpdateMessageState(StatesGroup):
    text = State()
    day_of_week = State()
    time = State()
    confirm = State()

@message_for_new_router.message(F.text == AdminKeyboard.admin_text_kb['message_for_new'])
async def start_update_message(message: Message, state: FSMContext, i18n, session_without_commit):
    try:
        await state.set_state(UpdateMessageState.text)
        await message.answer("<b>Напоминание</b>:" \
        "\n- Вы можете использовать HTML теги для форматирования текста." \
        "\n- Максимальная длина сообщения: 1000 символов."
        "\n- Отправляться сообщение будет всегда при первом заходе в бота и по заданному рассписанию " \
        "\n- При повторном заполнение формы - старое сообщение убирается" \
        "\n- К сообщениям будут прикрепленны кнопки 'Активировать Промокод' и 'Получить промокод'" )
        message_for_new_dao = MessageForNewDAO(session_without_commit)
        message_ru = await message_for_new_dao.get_by_lang_code('ru')
        message_en = await message_for_new_dao.get_by_lang_code('en')
        if message_ru and message_en:
            days_dict = {
                'mon' : 'Понедельник',
                'tue': 'Вторник',
                'wed': 'Среда',
                'thu': 'Четверг',
                'fri': 'Пятница',
                'sat': 'Суббота',
                'sun': 'Воскресенье'
            }
            selected_days = [list(days_dict.keys()).index(day) for day in message_ru.dispatch_day.split(',') if day in days_dict]
            day_of_week_for_view = ', '.join([days_dict[day] for day in sorted(selected_days)])
            await message.answer(f"Найдено существующее сообщение для новых пользователей.\n\n"
                                 f"<b>ru:</b>\n{message_ru.text}\n\n"
                                 f"<b>en:</b>\n{message_en.text}\n\n"
                                 f"<b>Дни недели:</b> {day_of_week_for_view}\n"
                                 f"<b>Время отправки:</b> {message_ru.dispatch_time}\n\n")
            return
        await message.answer("Введите текст сообщения для новых пользователей:",reply_markup=get_cancel_kb(i18n))
    except Exception as e:
        logger.error(f"Ошибка при начале обновления сообщения: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@message_for_new_router.message(F.text.in_(get_all_locales_for_key(translator_hub, "keyboard-reply-cancel")),
                             StateFilter(UpdateMessageState))
async def cancel_update_message(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(GeneralStates.admin_panel)
    await message.answer(
        message.text,
        reply_markup=AdminKeyboard.build()
    )

days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

@message_for_new_router.message(StateFilter(UpdateMessageState.text), F.text)
async def receive_message_text(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        if len(message.text) > 1000:
            await message.answer("Ошибка: Длина сообщения превышает 4096 символов. Пожалуйста, введите более короткое сообщение.")
            return
        text_ru = data.get("text_ru")
        if not text_ru:
            await state.update_data(text_ru=message.text)
            await message.answer("Введите текст сообщения на английском языке:")
            return
        if text_ru:
            await state.update_data(text_en=message.text)
            await state.set_state(UpdateMessageState.day_of_week)
            await message.answer("Выберите дни недели:",reply_markup=get_paginated_checkbox_keyboard(
                items=days,
                context="messsage_for_new_days_selection",
                get_display_text=lambda x: x,
                get_item_id=lambda x: days.index(x),
                selected_ids=[],
                page=0,
                items_per_page=7,
            ))
    except Exception as e:
        logger.error(f"Ошибка при получении текста сообщения: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@message_for_new_router.callback_query(PaginatedCheckboxCallback.filter(F.context == "messsage_for_new_days_selection"))
async def handle_day_selection(callback: CallbackQuery, callback_data: PaginatedCheckboxCallback, state: FSMContext):
    try:
        data = await state.get_data()
        selected_days = set(data.get("selected_days", []))
        
        if callback_data.action == "toggle":
            if callback_data.item_id in selected_days:
                selected_days.remove(callback_data.item_id)
            else:
                selected_days.add(callback_data.item_id)
            await state.update_data(selected_days=list(selected_days))
            await callback.message.edit_reply_markup(
                reply_markup=get_paginated_checkbox_keyboard(
                    items=days,
                    context="messsage_for_new_days_selection",
                    get_display_text=lambda x: x,
                    get_item_id=lambda x: days.index(x),
                    selected_ids=selected_days,
                    page=callback_data.page,
                    items_per_page=7,
                )
            )
        elif callback_data.action in ["prev", "next"]:
            await callback.message.edit_reply_markup(
                reply_markup=get_paginated_checkbox_keyboard(
                    items=days,
                    context="messsage_for_new_days_selection",
                    get_display_text=lambda x: x,
                    get_item_id=lambda x: days.index(x),
                    selected_ids=selected_days,
                    page=callback_data.page,
                    items_per_page=7,
                )
            )
        elif callback_data.action == "done":
            if not selected_days:
                await callback.answer("Пожалуйста, выберите хотя бы один день.", show_alert=True)
                return
            #mon,tue,wed,thu,fri,sat,sun
            days_dict = {
                0 : 'mon',
                1: 'tue',
                2: 'wed',
                3: 'thu',
                4: 'fri',
                5: 'sat',
                6: 'sun'
            }
            day_of_week_view = ', '.join([days[day] for day in sorted(selected_days)])
            day_of_week_data = ','.join([days_dict[day] for day in sorted(selected_days)])
            await state.update_data(day_of_week_for_view=day_of_week_view)
            await state.update_data(day_of_week=day_of_week_data)
            await state.set_state(UpdateMessageState.time)
            await callback.message.delete()
            await callback.message.answer("Введите время отправки сообщения в формате ЧЧ:ММ (например, 14:30):")
    except Exception as e:
        logger.error(f"Ошибка при выборе дней недели: {e}")
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)

@message_for_new_router.message(StateFilter(UpdateMessageState.time), F.text)
async def receive_time(message: Message, state: FSMContext,i18n):
    try:
        time_parts = message.text.split(":")
        if len(time_parts) != 2 or not all(part.isdigit() for part in time_parts):
            await message.answer("Неверный формат времени. Пожалуйста, используйте формат ЧЧ:ММ (например, 14:30).")
            return
        hours, minutes = map(int, time_parts)
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            await message.answer("Неверное время. Часы должны быть от 00 до 23, минуты от 00 до 59.")
            return
        formatted_time = f"{hours:02}:{minutes:02}"
        await state.update_data(time=formatted_time)
        data = await state.get_data()
        text = '<b>ru:</b>\n' + data.get("text_ru") + "\n\n<b>en:</b>\n" + data.get("text_en")
        time = data.get("time")
        day_of_week_for_view = data.get("day_of_week_for_view")
        confirm_text = f"Пожалуйста, подтвердите введённые данные:\n\n" \
                       f"<b>Текст сообщения:</b>\n{text}\n\n" \
                       f"<b>Дни недели:</b> {day_of_week_for_view}\n" \
                       f"<b>Время отправки:</b> {time}\n\n" \
                       "Если всё верно, нажмите 'Подтвердить'. Если хотите изменить, нажмите 'Отмена'."
        
        await state.set_state(UpdateMessageState.confirm)
        await message.answer(confirm_text, reply_markup=get_confrim_kb(i18n, context="message_for_new_confirm"))
    except Exception as e:
        logger.error(f"Ошибка при получении времени: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова.")

@message_for_new_router.callback_query(ConfrimCallback.filter(F.context == "message_for_new_confirm"))
async def handle_confirmation(callback: CallbackQuery, callback_data: ConfrimCallback, state:FSMContext, session_without_commit):
    try:
        await callback.message.delete()
        data = await state.get_data()
        if callback_data.action == "confirm":
            text_ru = data.get("text_ru")
            text_en = data.get("text_en")
            day_of_week = data.get("day_of_week")
            time = data.get("time")
            message_dao = MessageForNewDAO(session_without_commit)
            await message_dao.upsert_message_for_new(
                dispatch_day=day_of_week,
                dispatch_time=time,
                text=text_ru,
                lang_code='ru'
            )
            await message_dao.upsert_message_for_new(
                dispatch_day=day_of_week,
                dispatch_time=time,
                text=text_en,
                lang_code='en'
            )
            try:
                if day_of_week and time:
                    hour, minute = map(int, time.split(":"))
                    moscow_tz = ZoneInfo("Europe/Moscow")
                    scheduler.add_job(
                        check_and_notify_gift,
                        CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute,timezone=moscow_tz),
                        id="gift_notification",
                        replace_existing=True
                    )
            except Exception as sch_e:
                logger.error(f"Ошибка при обновлении задачи рассылки: {sch_e}")
            await state.clear()
            await callback.message.answer("Сообщение для новых пользователей успешно обновлено.", 
                                          reply_markup=AdminKeyboard.build())
            await session_without_commit.commit()
        if callback_data.action == "back":
            await state.clear()
            await state.set_state(GeneralStates.admin_panel)
            await callback.message.answer("Обновление сообщения отменено. Вы можете начать заново, нажав соответствующую кнопку в админ-панели.", 
                                            reply_markup=AdminKeyboard.build())
    except Exception as e:
        logger.error(f"Ошибка при обработке подтверждения: {e}")
        await callback.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)