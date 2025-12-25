import os
import sys
import logging
import json
import asyncio
import requests
from redis import Redis
from rq import Worker, Queue  # ✅ БЕЗ Connection
from bot.common.func.hint_viewer import process_mat_file
from bot.common.service.sync_folder_service import SyncthingSync
from bot.config import settings
from bot.common.func.hint_viewer import extract_player_names
from bot.routers.hint_viewer_router import remove_active_job

# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

syncthing_sync = SyncthingSync()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Два варианта подключения:
# 1. Если используешь ACL-пользователя
REDIS_USER = os.getenv("REDIS_USER")
REDIS_USER_PASSWORD = os.getenv("REDIS_USER_PASSWORD")

# 2. Если используешь default пароль
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

# Выбираем какой использовать
if REDIS_USER and REDIS_USER_PASSWORD:
    # С ACL-пользователем
    redis_url = f"redis://{REDIS_USER}:{REDIS_USER_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    logger.info(f"Connecting to Redis with ACL user: {REDIS_USER}")
else:
    # С default пользователем (только пароль)
    redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    logger.info(f"Connecting to Redis with default user")

logger.info(f"Redis URL: redis://<user>:<pass>@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

redis_conn = Redis.from_url(redis_url, decode_responses=False)


def analyze_backgammon_job(mat_path: str, json_path: str, user_id: str):
    """
    Анализирует один .mat файл (запускается в worker-е).

    Args:
        mat_path: Путь к исходному .mat файлу
        json_path: Путь для сохранения результата .json
        user_id: ID пользователя (для логирования)

    Returns:
        dict: Результат анализа (success/error)
    """
    try:
        logger.info(f"[Job Start] mat_path={mat_path}, user_id={user_id}")

        process_mat_file(mat_path, json_path, user_id)

        # Проверяем что результат создан
        games_dir = json_path.rsplit(".", 1)[0] + "_games"
        has_games = os.path.exists(games_dir) and any(
            f.endswith(".json") for f in os.listdir(games_dir)
        )

        logger.info(
            f"[Job Completed] {mat_path} -> {json_path} (has_games={has_games})"
        )
        if not asyncio.run(syncthing_sync.sync_and_wait(max_wait=30)):
            logger.warning("Ошибка синхронизации Syncthing")
        return {
            "status": "success",
            "mat_path": mat_path,
            "json_path": json_path,
            "games_dir": games_dir,
            "has_games": has_games,
        }

    except Exception as e:
        logger.exception(f"[Job Failed] {mat_path}")
        return {"status": "error", "error": str(e), "mat_path": mat_path}


def analyze_backgammon_batch_job(
    file_paths: list, user_id: str, batch_id: str, job_id: str = None
):
    """
    Анализирует пакет .mat файлов последовательно (запускается в worker-е).
    Отправляет результаты по мере обработки каждого файла.

    Args:
        file_paths: Список путей к .mat файлам
        user_id: ID пользователя
        batch_id: ID батча для группировки
        chat_id: ID чата для отправки сообщений
        bot_token: Токен бота для Telegram API

    Returns:
        dict: Результаты анализа для каждого файла
    """
    results = []
    total_files = len(file_paths)

    logger.info(
        f"[Batch Job Start] batch_id={batch_id}, files={total_files}, user_id={user_id}"
    )

    def send_telegram_message(text, parse_mode="Markdown"):
        """Отправляет сообщение в Telegram через API"""
        try:
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
            data = {"chat_id": int(user_id), "text": text, "parse_mode": parse_mode}
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Failed to send Telegram message: {response.text}")
        except Exception as e:
            logger.warning(f"Error sending Telegram message: {e}")

    for idx, mat_path in enumerate(file_paths):
        fname = os.path.basename(mat_path)
        logger.info(f"[Batch Processing] {idx + 1}/{total_files}: {fname}")

        try:
            # Генерируем уникальный ID для файла
            game_id = f"{batch_id}_{idx}"
            json_path = f"files/{game_id}.json"

            # Обрабатываем файл
            process_mat_file(mat_path, json_path, user_id)

            # Проверяем результат
            games_dir = json_path.rsplit(".", 1)[0] + "_games"
            has_games = os.path.exists(games_dir) and any(
                f.endswith(".json") for f in os.listdir(games_dir)
            )

            logger.info(
                f"[Batch File Completed] {fname} -> {json_path} (has_games={has_games})"
            )

            # Отправляем результат пользователю
            if has_games:
                # Извлекаем имена игроков
                try:
                    with open(mat_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    red_player, black_player = extract_player_names(content)
                except Exception:
                    red_player, black_player = "Red", "Black"

                # Создаем inline клавиатуру (упрощенная версия)
                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "Просмотр всех ходов",
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=0"
                                },
                            }
                        ],
                        [
                            {
                                "text": "Только ошибки (оба игрока)",
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=1"
                                },
                            }
                        ],
                        [
                            {
                                "text": f"Только ошибки ({red_player})",
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=2"
                                },
                            }
                        ],
                        [
                            {
                                "text": f"Только ошибки ({black_player})",
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=3"
                                },
                            }
                        ],
                        [
                            {
                                "text": "Показать статистику игры",
                                "callback_data": f"show_stats:{game_id}",
                            }
                        ],
                    ]
                }
                if not asyncio.run(syncthing_sync.sync_and_wait(max_wait=30)):
                    logger.warning("Ошибка синхронизации Syncthing")
                send_telegram_message(
                    f"✅ **{fname}** обработан!\n{red_player} vs {black_player}",
                    parse_mode="Markdown",
                )
                # Отправляем клавиатуру отдельно (упрощенная версия)
                try:
                    url = (
                        f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
                    )
                    data = {
                        "chat_id": int(user_id),
                        "text": "Выберите вариант просмотра ошибок:",
                        "reply_markup": json.dumps(keyboard),
                    }
                    requests.post(url, data=data, timeout=10)
                except Exception as e:
                    logger.warning(f"Error sending keyboard: {e}")
            else:
                send_telegram_message(
                    f"✅ **{fname}** обработан, но игр не найдено.",
                    parse_mode="Markdown",
                )

            results.append(
                {
                    "file_index": idx + 1,
                    "mat_path": mat_path,
                    "json_path": json_path,
                    "games_dir": games_dir,
                    "has_games": has_games,
                    "status": "success",
                }
            )

        except Exception as e:
            logger.exception(f"[Batch File Failed] {fname}")
            send_telegram_message(
                f"❌ **{fname}**: {str(e)[:100]}", parse_mode="Markdown"
            )
            results.append(
                {
                    "file_index": idx + 1,
                    "mat_path": mat_path,
                    "status": "error",
                    "error": str(e),
                }
            )

    logger.info(
        f"[Batch Job Completed] batch_id={batch_id}, processed={len(results)}/{total_files}"
    )

    # Отправляем итоговое сообщение
    successful = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - successful
    send_telegram_message(
        f"🎉 **Пакетная обработка завершена!**\n\n✅ Успешно: {successful}\n❌ Ошибок: {failed}\n📊 Всего: {total_files}",
        parse_mode="Markdown",
    )
    logger.info(f"Removing active job: user_id={user_id}, job_id={job_id or batch_id}")
    remove_active_job(user_id, job_id or batch_id)
    return {
        "batch_id": batch_id,
        "total_files": total_files,
        "results": results,
        "status": "completed",
    }


if __name__ == "__main__":
    try:
        redis_conn.ping()
        logger.info(f"✅ Connected to Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis: {e}")
        sys.exit(1)

    # Queue и Worker используют тот же connection с decode_responses=False
    try:
        queue_analysis = Queue("backgammon_analysis", connection=redis_conn)
        queue_batch = Queue("backgammon_batch_analysis", connection=redis_conn)
        worker = Worker([queue_analysis, queue_batch], connection=redis_conn)
        logger.info(
            f"🚀 Starting Worker on queues 'backgammon_analysis' and 'backgammon_batch_analysis'..."
        )
        worker.work()
    except Exception as e:
        logger.exception("Worker crashed with error")
        sys.exit(1)
