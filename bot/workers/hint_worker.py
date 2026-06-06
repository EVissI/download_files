import os
import sys
import logging
import tempfile
from redis import Redis
from rq import Worker, Queue
from bot.common.func.hint_viewer import process_mat_file, extract_player_names
from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.hint_job_state import publish_batch_file_ready
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
    Уведомления в Telegram — только на стороне бота (check_job_status).
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
    original_fnames: list | None = None,
    job_id: str = None,
):
    """
    mat_s3_keys: ключи входных .mat в S3 (например hints/batch_in/...).
    Статусы файлов пишет в Redis; Telegram — только бот (check_batch_job_status).
    """
    results = []
    total_files = len(mat_s3_keys)
    s3 = HintS3Storage.from_settings()
    original_fnames = original_fnames or []

    logger.info(
        f"[Batch Job Start] batch_id={batch_id}, files={total_files}, user_id={user_id}"
    )

    for idx, input_mat_key in enumerate(mat_s3_keys):
        fname = (
            original_fnames[idx]
            if idx < len(original_fnames)
            else os.path.basename(input_mat_key)
        )
        next_fname = (
            original_fnames[idx + 1]
            if idx + 1 < len(original_fnames)
            else None
        )
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

            sync_redis_client.set(f"mat_path:{game_id}", mat_key, ex=7200)

            publish_batch_file_ready(
                batch_id,
                idx,
                {
                    "status": "success",
                    "fname": fname,
                    "next_fname": next_fname,
                    "game_id": game_id,
                    "mat_path": mat_key,
                    "has_games": has_games,
                    "red_player": red_player,
                    "black_player": black_player,
                },
            )

            logger.info(
                f"[Batch File Completed] {fname} -> {mat_key} (has_games={has_games})"
            )
            results.append(
                {
                    "file_index": idx + 1,
                    "mat_path": mat_key,
                    "has_games": has_games,
                    "status": "success",
                }
            )

        except Exception as e:
            logger.exception(f"[Batch File Failed] {fname}")
            publish_batch_file_ready(
                batch_id,
                idx,
                {
                    "status": "error",
                    "fname": fname,
                    "next_fname": next_fname,
                    "error": str(e)[:200],
                },
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
