import os
import sys
import logging
import json
import tempfile
import requests
from redis import Redis
from rq import Worker, Queue
from bot.common.func.hint_viewer import process_mat_file
from bot.common.service.hint_s3_service import HintS3Storage
from bot.config import settings
from bot.common.func.hint_viewer import extract_player_names
from bot.routers.hint_viewer_router import remove_active_job

from bot.db.redis import sync_redis_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

REDIS_USER = os.getenv("REDIS_USER")
REDIS_USER_PASSWORD = os.getenv("REDIS_USER_PASSWORD")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
text = {
    "hint_viewer_finished": {
        "en": "✅ Analysis completed!\n{red_player} vs {black_player}\n",
        "ru": "✅ Анализ завершен!\n{red_player} vs {black_player}\n",
    },
    "hint_viewer_butn_1": {"en": "View all moves", "ru": "Просмотр всех ходов"},
    "hint_viewer_butn_2": {
        "en": "Only mistakes (both players)",
        "ru": "Только ошибки (оба игрока)",
    },
    "hint_viewer_butn_3": {
        "en": "Only mistakes ({red_player})",
        "ru": "Только ошибки ({red_player})",
    },
    "hint_viewer_butn_4": {
        "en": "Only mistakes ({black_player})",
        "ru": "Только ошибки ({black_player})",
    },
    "hint_viewer_butn_5": {
        "en": "Show game statistics",
        "ru": "Показать статистику игры",
    },
}
if REDIS_USER and REDIS_USER_PASSWORD:
    redis_url = f"redis://{REDIS_USER}:{REDIS_USER_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    logger.info(f"Connecting to Redis with ACL user: {REDIS_USER}")
else:
    redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    logger.info("Connecting to Redis with default user")

logger.info(f"Redis URL: redis://<user>:<pass>@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

redis_conn = Redis.from_url(redis_url, decode_responses=False)


def _upload_hint_results(
    s3: HintS3Storage,
    game_id: str,
    local_mat: str,
    local_json: str,
) -> tuple[str, bool]:
    """Загружает .mat, сводный JSON и каталог игр в S3. Возвращает ключ .mat и has_games."""
    dest_mat_key = s3.mat_key(game_id)
    s3.upload_file(local_mat, dest_mat_key)
    s3.upload_file(
        local_json,
        s3.summary_json_key(game_id),
        content_type="application/json",
    )
    games_dir = local_json.rsplit(".", 1)[0] + "_games"
    if os.path.isdir(games_dir):
        s3.upload_tree(games_dir, s3.games_prefix(game_id))
    has_games = s3.games_have_any_json(game_id)
    return dest_mat_key, has_games


def analyze_backgammon_job(game_id: str, user_id: str, job_id: str = None):
    """
    Анализирует один .mat: источник в S3 hints/{game_id}.mat, результат туда же.
    """
    s3 = HintS3Storage.from_settings()
    src_key = s3.mat_key(game_id)
    try:
        logger.info(f"[Job Start] game_id={game_id}, s3_key={src_key}, user_id={user_id}")

        with tempfile.TemporaryDirectory() as tmp:
            local_mat = os.path.join(tmp, "source.mat")
            s3.download_file(src_key, local_mat)
            local_json = os.path.join(tmp, f"{game_id}.json")
            process_mat_file(local_mat, local_json, user_id)

            mat_key, has_games = _upload_hint_results(s3, game_id, local_mat, local_json)

        sync_redis_client.set(f"mat_path:{game_id}", mat_key, ex=86400)

        logger.info(
            f"[Job Completed] game_id={game_id} -> {mat_key} (has_games={has_games})"
        )
        return {
            "status": "success",
            "mat_path": mat_key,
            "has_games": has_games,
            "game_id": game_id,
        }

    except Exception as e:
        logger.exception(f"[Job Failed] game_id={game_id}")
        return {
            "status": "error",
            "error": str(e),
            "mat_path": src_key,
            "game_id": game_id,
        }


def analyze_backgammon_batch_job(
    mat_s3_keys: list,
    user_id: str,
    batch_id: str,
    job_id: str = None,
    lang_code: str = "en",
):
    """
    mat_s3_keys: ключи входных .mat в S3 (например hints/batch_in/...).
    """
    results = []
    total_files = len(mat_s3_keys)
    s3 = HintS3Storage.from_settings()

    logger.info(
        f"[Batch Job Start] batch_id={batch_id}, files={total_files}, user_id={user_id}"
    )

    def send_telegram_message(text, parse_mode="Markdown"):
        try:
            url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
            data = {"chat_id": int(user_id), "text": text, "parse_mode": parse_mode}
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Failed to send Telegram message: {response.text}")
        except Exception as e:
            logger.warning(f"Error sending Telegram message: {e}")

    for idx, input_mat_key in enumerate(mat_s3_keys):
        fname = os.path.basename(input_mat_key)
        logger.info(f"[Batch Processing] {idx + 1}/{total_files}: {fname}")

        try:
            game_id = f"{batch_id}_{idx}"

            with tempfile.TemporaryDirectory() as tmp:
                local_mat = os.path.join(tmp, "source.mat")
                s3.download_file(input_mat_key, local_mat)
                local_json = os.path.join(tmp, f"{game_id}.json")
                process_mat_file(local_mat, local_json, user_id)

                mat_key, has_games = _upload_hint_results(
                    s3, game_id, local_mat, local_json
                )

                if has_games:
                    try:
                        with open(local_mat, "r", encoding="utf-8") as f:
                            content = f.read()
                        red_player, black_player = extract_player_names(content)
                    except Exception:
                        red_player, black_player = "Red", "Black"
                else:
                    red_player, black_player = "Red", "Black"

            logger.info(
                f"[Batch File Completed] {fname} -> {mat_key} (has_games={has_games})"
            )

            if has_games:

                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": text["hint_viewer_butn_1"][lang_code],
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=0"
                                },
                            }
                        ],
                        [
                            {
                                "text": text["hint_viewer_butn_2"][lang_code],
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=1"
                                },
                            }
                        ],
                        [
                            {
                                "text": text["hint_viewer_butn_3"][lang_code].format(
                                    red_player=red_player
                                ),
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=2"
                                },
                            }
                        ],
                        [
                            {
                                "text": text["hint_viewer_butn_4"][lang_code].format(
                                    black_player=black_player
                                ),
                                "web_app": {
                                    "url": f"{settings.MINI_APP_URL}/hint-viewer?game_id={game_id}&error=3"
                                },
                            }
                        ],
                        [
                            {
                                "text": text["hint_viewer_butn_5"][lang_code],
                                "callback_data": f"show_stats:{game_id}",
                            }
                        ],
                    ]
                }
                send_telegram_message(
                    f"✅ <b>{fname}</b> обработан!\n{red_player} vs {black_player}",
                    parse_mode="HTML",
                )
                try:
                    url = (
                        f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
                    )
                    data = {
                        "chat_id": int(user_id),
                        "text": text["hint_viewer_finished"][lang_code].format(
                            red_player=red_player, black_player=black_player
                        ),
                        "reply_markup": json.dumps(keyboard),
                    }
                    requests.post(url, data=data, timeout=10)
                except Exception as e:
                    logger.warning(f"Error sending keyboard: {e}")
            else:
                send_telegram_message(
                    f"✅ <b>{fname}</b> обработан, но игр не найдено.",
                    parse_mode="HTML",
                )

            results.append(
                {
                    "file_index": idx + 1,
                    "mat_path": mat_key,
                    "has_games": has_games,
                    "status": "success",
                }
            )
            sync_redis_client.set(f"mat_path:{game_id}", mat_key, ex=7200)

        except Exception as e:
            logger.exception(f"[Batch File Failed] {fname}")
            send_telegram_message(
                f"❌ <b>{fname}</b>: {str(e)[:100]}", parse_mode="HTML"
            )
            results.append(
                {
                    "file_index": idx + 1,
                    "mat_path": input_mat_key,
                    "status": "error",
                    "error": str(e),
                }
            )

    logger.info(
        f"[Batch Job Completed] batch_id={batch_id}, processed={len(results)}/{total_files}"
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

    try:
        queue_analysis = Queue("backgammon_analysis", connection=redis_conn)
        queue_batch = Queue("backgammon_batch_analysis", connection=redis_conn)
        worker = Worker([queue_analysis, queue_batch], connection=redis_conn)
        logger.info(
            "🚀 Starting Worker on queues 'backgammon_analysis' and 'backgammon_batch_analysis'..."
        )
        worker.work()
    except Exception as e:
        logger.exception("Worker crashed with error")
        sys.exit(1)
