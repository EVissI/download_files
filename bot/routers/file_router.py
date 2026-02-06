import os
import uuid
import json
import asyncio
import shutil
import zipfile
import io
from datetime import datetime
import pytz
from aiogram import Router, F
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    BufferedInputFile,
    WebAppInfo,
    Document,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from bot.common.filters.user_info import UserInfo
from bot.db.dao import MessagesTextsDAO, UserDAO
from bot.db.schemas import SUser
from bot.db.models import User
from bot.db.redis import redis_client
from bot.routers.short_board import ShortBoardDialog
from bot.routers.hint_viewer_router import (
    HintViewerStates,
    can_enqueue_job,
    add_active_job,
    task_queue,
    redis_rq,
    get_queue_position_message,
    check_job_status,
)
from bot.routers.autoanalize.autoanaliz import AutoAnalyzeDialog, analyze_file_by_path
from bot.common.func.game_parser import parse_file, get_names
from bot.common.func.yadisk import save_file_to_yandex_disk
from bot.common.func.hint_viewer import (
    extract_player_names,
    estimate_processing_time,
    random_filename,
)
from bot.common.func.waiting_message import WaitingMessageManager
from bot.common.service.sync_folder_service import SyncthingSync
from bot.common.kbds.markup.main_kb import MainKeyboard
from bot.common.kbds.inline.autoanalize import get_download_pdf_kb, get_hint_viewer_kb
from bot.config import bot, settings, translator_hub

file_router = Router()


class FileSelectionStates:
    """Временное состояние для выбора обработчика файла"""
    pass


@file_router.message(
    F.document & F.document.file_name.endswith(".mat"),
    UserInfo(), StateFilter(None),
)
async def handle_mat_file_outside_fsm(
    message: Message,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
):
    """
    Перехватывает .mat файлы вне контекста FSM состояния
    и предлагает выбрать обработчик через инлайн кнопки
    """
    try:
        # Проверяем, что пользователь не находится в активном FSM состоянии
        current_state = await state.get_state()
        if current_state:
            # Если есть активное состояние, пропускаем обработку
            # Пусть другие роутеры обработают файл
            return
        
        messages_dao = MessagesTextsDAO(session_without_commit)
        file = message.document
        
        # Проверяем, что это действительно .mat файл
        if not file.file_name.lower().endswith(".mat"):
            return
        
        # Создаем временную директорию для файла
        temp_dir = os.path.join(os.getcwd(), "files", "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Генерируем уникальное имя файла
        temp_file_id = str(uuid.uuid4())
        temp_file_name = f"{temp_file_id}_{file.file_name}"
        temp_file_path = os.path.join(temp_dir, temp_file_name)
        
        # Скачиваем файл
        await message.bot.download(file.file_id, destination=temp_file_path)
        
        # Сохраняем информацию о файле в state
        await state.update_data(
            temp_file_path=temp_file_path,
            temp_file_id=temp_file_id,
            original_file_name=file.file_name,
            original_file_id=file.file_id,
        )
        
        # Создаем инлайн клавиатуру с выбором обработчика
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=await messages_dao.get_text("file_router_short_board", user_info.lang_code) or "Просмотр доски",
                        callback_data=f"file_handler:short_board:{temp_file_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await messages_dao.get_text("file_router_hint_viewer", user_info.lang_code) or "Анализ ошибок",
                        callback_data=f"file_handler:hint_viewer:{temp_file_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=await messages_dao.get_text("file_router_auto_analyze", user_info.lang_code) or "Автоанализ",
                        callback_data=f"file_handler:auto_analyze:{temp_file_id}",
                    )
                ],
            ]
        )
        
        await message.answer(
            await messages_dao.get_text("file_router_choose_handler", user_info.lang_code) or "Выберите способ обработки файла:",
            reply_markup=keyboard,
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке файла вне FSM: {e}")
        await message.answer("Произошла ошибка при обработке файла. Попробуйте снова.")


@file_router.callback_query(F.data.startswith("file_handler:"), UserInfo())
async def handle_file_handler_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
):
    """
    Обрабатывает выбор обработчика файла и перенаправляет файл в соответствующий роутер
    """
    try:
        messages_dao = MessagesTextsDAO(session_without_commit)
        parts = callback.data.split(":")
        handler_type = parts[1]
        temp_file_id = parts[2]
        
        # Получаем данные о файле из state
        data = await state.get_data()
        temp_file_path = data.get("temp_file_path")
        original_file_name = data.get("original_file_name")
        original_file_id = data.get("original_file_id")
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            await callback.answer("Файл не найден. Пожалуйста, загрузите файл снова.")
            await callback.message.delete()
            await state.clear()
            return
        
        await callback.message.delete()
        await callback.answer()
        
        # Создаем временное сообщение с документом для передачи в обработчик
        # Вместо этого мы можем напрямую вызвать обработчик с путем к файлу
        
        if handler_type == "short_board":
            # Перенаправляем в short_board_router
            await state.set_state(ShortBoardDialog.file)
            
            # Скачиваем файл в нужное место для short_board
            dir_name = str(uuid.uuid4())
            files_dir = os.path.join(os.getcwd(), "files", dir_name)
            os.makedirs(files_dir, exist_ok=True)
            
            file_name = original_file_name.replace(" ", "").replace(".txt", ".mat")
            file_path = os.path.join(files_dir, file_name)
            
            # Копируем файл
            shutil.copy(temp_file_path, file_path)
            
            # Удаляем временный файл
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            # Читаем содержимое файла
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            
            # Создаем фиктивное сообщение для передачи в обработчик
            # Вместо этого вызываем логику напрямую
            await process_short_board_file(
                callback.message.chat.id,
                file_path,
                file_content,
                user_info,
                session_without_commit,
                state,
            )
            
        elif handler_type == "hint_viewer":
            # Перенаправляем в hint_viewer_router
            await state.set_state(HintViewerStates.waiting_file)
            
            # Перемещаем файл в нужное место
            files_dir = os.path.join(os.getcwd(), "files")
            os.makedirs(files_dir, exist_ok=True)
            file_path = os.path.join(files_dir, original_file_name)
            
            shutil.copy(temp_file_path, file_path)
            
            # Удаляем временный файл
            try:
                os.remove(temp_file_path)
            except:
                pass
            
            # Вызываем обработчик hint_viewer напрямую
            await process_hint_viewer_file(
                callback.message.chat.id,
                file_path,
                original_file_name,
                user_info,
                session_without_commit,
                state,
            )
            
        elif handler_type == "auto_analyze":
            # Перенаправляем в auto_analyze_router
            # Сначала нужно выбрать тип анализа (moneygame/match)
            await state.set_state(AutoAnalyzeDialog.file)
            
            # Сохраняем путь к файлу
            await state.update_data(
                temp_file_path=temp_file_path,
                original_file_name=original_file_name,
            )
            
            # Показываем выбор типа анализа
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(
                text=await messages_dao.get_text('analyze_moneygame', user_info.lang_code) or "Деньги",
                callback_data=f"file_auto_type:moneygame:{temp_file_id}"
            )
            keyboard.button(
                text=await messages_dao.get_text('analyze_match', user_info.lang_code) or "Матч",
                callback_data=f"file_auto_type:match:{temp_file_id}"
            )
            keyboard.adjust(1)
            
            await callback.message.answer(
                await messages_dao.get_text('analyze_choose_game_type', user_info.lang_code) or "Выберите тип игры:",
                reply_markup=keyboard.as_markup()
            )
            # Не очищаем state для auto_analyze, так как нужно сохранить данные для выбора типа
            return
        
        # Очищаем state только для других обработчиков
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при перенаправлении файла: {e}")
        await callback.message.answer("Произошла ошибка при обработке файла.")
        await state.clear()


@file_router.callback_query(F.data.startswith("file_auto_type:"), UserInfo())
async def handle_auto_type_selection(
    callback: CallbackQuery,
    state: FSMContext,
    user_info: User,
    session_without_commit: AsyncSession,
):
    """Обрабатывает выбор типа анализа для автоанализа"""
    try:
        messages_dao = MessagesTextsDAO(session_without_commit)
        parts = callback.data.split(":")
        analysis_type = parts[1]
        temp_file_id = parts[2]
        
        # Получаем данные о файле
        data = await state.get_data()
        temp_file_path = data.get("temp_file_path")
        original_file_name = data.get("original_file_name")
        
        if not temp_file_path or not os.path.exists(temp_file_path):
            await callback.answer("Файл не найден.")
            await callback.message.delete()
            await state.clear()
            return
        
        await callback.message.delete()
        await callback.answer()
        
        # Устанавливаем состояние и тип анализа
        await state.set_state(AutoAnalyzeDialog.file)
        await state.update_data(analysis_type=analysis_type)
        
        # Перемещаем файл в нужное место
        files_dir = os.path.join(os.getcwd(), "files")
        os.makedirs(files_dir, exist_ok=True)
        file_name = original_file_name.replace(" ", "").replace(".txt", ".mat")
        file_path = os.path.join(files_dir, file_name)
        
        shutil.copy(temp_file_path, file_path)
        
        # Удаляем временный файл
        try:
            os.remove(temp_file_path)
        except:
            pass
        
        # Вызываем обработчик автоанализа
        await process_auto_analyze_file(
            callback.message.chat.id,
            file_path,
            file_name,
            analysis_type,
            user_info,
            session_without_commit,
            state,
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке автоанализа: {e}")
        await callback.message.answer("Произошла ошибка при обработке файла.")


async def process_short_board_file(
    chat_id: int,
    file_path: str,
    file_content: str,
    user_info,
    session_without_commit: AsyncSession,
    state: FSMContext,
):
    """Обрабатывает файл для short_board"""
    messages_dao = MessagesTextsDAO(session_without_commit)
    
    try:
        dir_name = os.path.basename(os.path.dirname(file_path))
        file_name = os.path.basename(file_path)
        
        await bot.send_message(chat_id, await messages_dao.get_text(
            "short_board_processing", user_info.lang_code
        ))
        
        names = get_names(file_content)
        
        # Создание файла для сохранения на ядиск
        moscow_tz = pytz.timezone("Europe/Moscow")
        current_date = datetime.now(moscow_tz).strftime("%d.%m.%y-%H.%M.%S")
        new_file_name = f"{current_date}:{names[0]}:{names[1]}.mat"
        new_file_path = os.path.join(os.path.dirname(file_path), new_file_name)
        
        import shutil
        shutil.copy(file_path, new_file_path)
        
        # Сохранение файла на яндекс диск
        try:
            asyncio.create_task(save_file_to_yandex_disk(new_file_path, new_file_name))
        except Exception as e:
            logger.error(f"Error saving file to Yandex Disk: {e}")
        
        # Парсим файл
        await parse_file(file_content, dir_name)
        
        # Путь к директории с JSON файлами
        json_dir_path = os.path.join("./files", dir_name)
        json_file_path = os.path.join(json_dir_path, "games.json")
        
        if os.path.exists(json_file_path):
            # Создаем ZIP архив
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(json_file_path, arcname="games.json")
                zip_file.write(file_path, arcname=file_name)
            
            zip_buffer.seek(0)
            zip_doc = BufferedInputFile(
                zip_buffer.getvalue(),
                filename=f"{names[0]}_vs_{names[1]}_analysis.zip",
            )
        
        # Создаем кнопку с веб-приложением
        button = InlineKeyboardButton(
            text=await messages_dao.get_text(
                "short_board_open_game", user_info.lang_code
            ),
            web_app=WebAppInfo(
                url=f"{settings.MINI_APP_URL}/board-viewer?game_id={dir_name}&chat_id={chat_id}"
            ),
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
        
        await bot.send_message(
            chat_id,
            await messages_dao.get_text(
                "short_board_ready", user_info.lang_code),
            reply_markup=keyboard,
        )
        
        await UserDAO(session_without_commit).decrease_analiz_balance(
            user_id=user_info.id, service_type="SHORT_BOARD"
        )
        await session_without_commit.commit()
        
    except Exception as e:
        logger.error(f"Ошибка при обработке файла short_board: {e}")
        await bot.send_message(chat_id, f"Произошла ошибка при обработке файла: {e}")
    finally:
        await state.clear()


async def process_hint_viewer_file(
    chat_id: int,
    file_path: str,
    file_name: str,
    user_info,
    session_without_commit: AsyncSession,
    state: FSMContext,
):
    """Обрабатывает файл для hint_viewer"""
    messages_dao = MessagesTextsDAO(session_without_commit)
    syncthing_sync = SyncthingSync()
    
    try:
        # Генерируем уникальный ID для задачи
        game_id = random_filename(ext="")
        json_path = f"files/{game_id}.json"
        job_id = f"hint_{user_info.id}_{uuid.uuid4().hex[:8]}"
        
        # Проверяем возможность добавления задачи
        if not can_enqueue_job(user_info.id):
            await bot.send_message(
                chat_id,
                await messages_dao.get_text("hint_viewer_sin_active_job_err", user_info.lang_code)
            )
            await state.clear()
            return
        
        logger.info(f"Файл готов к обработке: {file_path}")
        
        # Синхронизация с Syncthing (если нужно)
        if not await syncthing_sync.sync_and_wait(max_wait=30):
            logger.warning("Ошибка синхронизации Syncthing")
        
        if not await syncthing_sync.wait_for_file(file_path, max_wait=30):
            await bot.send_message(chat_id, "❌ Файл не найден после синхронизации")
            await state.clear()
            return
        
        # Читаем содержимое файла
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        red_player, black_player = extract_player_names(content)
        estimated_time = estimate_processing_time(file_path)
        
        # Добавляем задачу в очередь (используем task_queue из модуля)
        job = task_queue.enqueue(
            "bot.workers.hint_worker.analyze_backgammon_job",
            file_path,
            json_path,
            str(user_info.id),
            job_id=job_id,
            game_id=game_id,
        )
        
        # Используем реальный ID job, если он отличается от переданного
        actual_job_id = job.id if hasattr(job, 'id') and job.id else job_id
        logger.info(f"Job created: requested_job_id={job_id}, actual_job_id={actual_job_id}")
        
        # Сохраняем mat_path
        await redis_client.set(f"mat_path:{game_id}", file_path, expire=86400)
        
        add_active_job(user_info.id, actual_job_id)
        logger.info(f"Added active job: user_id={user_info.id}, job_id={actual_job_id}")
        
        # Сохраняем информацию о задаче (используем actual_job_id)
        await redis_client.set(
            f"job_info:{actual_job_id}",
            json.dumps({
                "game_id": game_id,
                "mat_path": file_path,
                "json_path": json_path,
                "red_player": red_player,
                "black_player": black_player,
                "user_id": user_info.id,
            }),
            expire=3600,
        )
        
        # Проверяем позицию в очереди
        queue_warning = await get_queue_position_message(
            redis_rq, ["backgammon_analysis", "backgammon_batch_analysis"], session_without_commit, user_info
        )
        if queue_warning:
            user_dao = UserDAO(session_without_commit)
            admins = await user_dao.find_all(filters=SUser(role=User.Role.ADMIN.value))
            for admin in admins:
                try:
                    await bot.send_message(
                        chat_id=admin.id,
                        text=f"Пользователь в очереди на анализ ошибок. Его сообщение:{queue_warning}\n",
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление админу {admin.id}: {e}")
            await bot.send_message(chat_id, queue_warning)
        
        status_text = await messages_dao.get_text(
            "hint_viewer_sin_file_accepted", user_info.lang_code, estimated_time=estimated_time
        )
        await bot.send_message(chat_id, status_text, parse_mode="Markdown")
        
        # Сохраняем данные в состояние для проверки статуса
        await state.update_data(
            job_id=actual_job_id,
            game_id=game_id,
            mat_path=file_path,
            json_path=json_path,
            red_player=red_player,
            black_player=black_player,
        )
        
        # Запускаем проверку статуса (используем actual_job_id)
        i18n = translator_hub.get_translator_by_locale(user_info.lang_code or "en")
        
        # Создаем фиктивное сообщение для check_job_status
        class FakeMessage:
            def __init__(self, chat_id, bot, user_id):
                self.chat = type('obj', (object,), {'id': chat_id})()
                self.bot = bot
                self.from_user = type('obj', (object,), {'id': user_id})()
                self._chat_id = chat_id
            
            async def answer(self, text, **kwargs):
                """Отправляет сообщение в чат через bot.send_message"""
                return await self.bot.send_message(chat_id=self._chat_id, text=text, **kwargs)
            
            async def reply(self, text, **kwargs):
                """Отправляет ответ на сообщение"""
                return await self.bot.send_message(chat_id=self._chat_id, text=text, **kwargs)
        
        fake_message = FakeMessage(chat_id, bot, user_info.id)
        asyncio.create_task(
            check_job_status(fake_message, actual_job_id, state, i18n, session_without_commit, user_info)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке файла hint_viewer: {e}")
        await bot.send_message(chat_id, f"Произошла ошибка при обработке файла: {e}")
        await state.clear()


async def process_auto_analyze_file(
    chat_id: int,
    file_path: str,
    file_name: str,
    analysis_type: str,
    user_info,
    session_without_commit: AsyncSession,
    state: FSMContext,
):
    """Обрабатывает файл для auto_analyze"""
    # Создаем фиктивное сообщение для передачи в обработчик
    class FakeDocument:
        def __init__(self, file_name, file_id):
            self.file_name = file_name
            self.file_id = file_id
    
    class FakeMessage:
        def __init__(self, chat_id, bot, document, user_id):
            self.chat = type('obj', (object,), {'id': chat_id})()
            self.bot = bot
            self.document = document
            self.from_user = type('obj', (object,), {'id': user_id})()
    
    # Создаем фиктивный документ
    fake_doc = FakeDocument(file_name, "fake_file_id")
    fake_message = FakeMessage(chat_id, bot, fake_doc, user_info.id)
    
    # Устанавливаем состояние и данные
    await state.set_state(AutoAnalyzeDialog.file)
    await state.update_data(analysis_type=analysis_type)
    
    messages_dao = MessagesTextsDAO(session_without_commit)
    i18n = translator_hub.get_translator_by_locale(user_info.lang_code or "en")
    
    try:
        waiting_manager = WaitingMessageManager(chat_id, bot, i18n)
        await waiting_manager.start()
        
        file_type = file_name.split(".")[-1]
        
        try:
            result = await analyze_file_by_path(
                file_path, file_type, user_info, session_without_commit, i18n, 
                fake_message, analysis_type, forward_message=True
            )
        except ValueError as e:
            await waiting_manager.stop()
            await state.clear()
            await bot.send_message(
                chat_id,
                str(e),
                reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
            )
            return
        
        if isinstance(result, tuple) and len(result) == 4:
            # Multiple players
            analysis_data, new_file_path, player_names, duration = result
            await state.update_data(
                analysis_data=analysis_data,
                file_name=os.path.basename(new_file_path),
                file_path=new_file_path,
                player_names=player_names,
                duration=duration,
            )
            
            keyboard = InlineKeyboardBuilder()
            for player in player_names:
                keyboard.button(text=player, callback_data=f"auto_player:{player}")
            keyboard.adjust(1)
            await waiting_manager.stop()
            await bot.send_message(
                chat_id,
                await messages_dao.get_text('analyze_complete_ch_player', user_info.lang_code),
                reply_markup=keyboard.as_markup(),
            )
        else:
            # Single player
            formatted_analysis, new_file_path = result
            await waiting_manager.stop()
            # Сохраняем путь к файлу в Redis для возможности отправки на анализ ошибок
            from bot.db.redis import redis_client
            await redis_client.set(
                f"auto_analyze_file_path:{user_info.id}", new_file_path, expire=3600
            )
            await bot.send_message(
                chat_id,
                f"{formatted_analysis}\n\n",
                parse_mode="HTML",
                reply_markup=MainKeyboard.build(user_role=user_info.role, i18n=i18n),
            )
            from bot.common.kbds.inline.autoanalize import get_download_pdf_kb, get_hint_viewer_kb
            # Добавляем кнопку для отправки на анализ ошибок
            await bot.send_message(
                chat_id,
                await messages_dao.get_text('analyze_ask_hints', user_info.lang_code) or 
                "Хотите отправить этот файл на анализ ошибок?",
                reply_markup=get_hint_viewer_kb(i18n, 'solo')
            )
            await bot.send_message(
                chat_id,
                await messages_dao.get_text('analyze_ask_pdf', user_info.lang_code),
                reply_markup=get_download_pdf_kb(i18n, 'solo')
            )
            await session_without_commit.commit()
            # Очищаем состояние после успешной обработки
            await state.clear()
            
    except Exception as e:
        await session_without_commit.rollback()
        logger.error(f"Ошибка при автоматическом анализе файла: {e}")
        await bot.send_message(chat_id, i18n.auto.analyze.error.parse())
        await state.clear()
