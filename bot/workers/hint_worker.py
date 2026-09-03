import gc
import os
import socket
import sys
import logging
import tempfile
from datetime import datetime, timezone
from redis import Redis
from rq import Worker, Queue
from bot.common.func.hint_viewer import process_mat_file, extract_player_names
from bot.common.service.hint_s3_service import HintS3Storage
from bot.common.hint_job_state import (
    calc_batch_job_timeout,
    publish_batch_completed,
    publish_batch_file_ready,
)
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


def _rq_job_id(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    try:
        from rq import get_current_job

        current = get_current_job()
        if current is not None:
            return current.id
    except Exception:
        logger.exception("get_current_job failed")
    return None


def _sync_web_history_from_job(job_id: str | None, result: dict) -> None:
    job_id = _rq_job_id(job_id)
    if not job_id:
        return
    try:
        from bot.common.service.hint_viewer_web_service import sync_web_history_status

        if result.get("status") == "error":
            sync_web_history_status(
                job_id,
                "error",
                game_id=result.get("game_id"),
                error_message=str(result.get("error") or "Ошибка анализа")[:400],
                finished=True,
            )
        else:
            sync_web_history_status(
                job_id,
                "done",
                game_id=result.get("game_id"),
                finished=True,
            )
    except Exception:
        logger.exception("web history sync from worker failed job_id=%s", job_id)


def _sync_web_history_batch_file(
    job_id: str | None,
    *,
    filename: str,
    game_id: str | None = None,
    error: str | None = None,
    red_player: str | None = None,
    black_player: str | None = None,
) -> None:
    job_id = _rq_job_id(job_id)
    if not job_id:
        return
    try:
        from bot.common.service.hint_viewer_web_service import sync_web_history_status

        if error:
            sync_web_history_status(
                job_id,
                "error",
                original_filename=filename,
                error_message=str(error)[:400],
                finished=True,
            )
        else:
            sync_web_history_status(
                job_id,
                "done",
                original_filename=filename,
                game_id=game_id,
                finished=True,
                red_player=red_player,
                black_player=black_player,
            )
    except Exception:
        logger.exception("web batch history sync failed job_id=%s file=%s", job_id, filename)


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
        result = {
            "status": "success",
            "mat_path": mat_key,
            "has_games": has_games,
            "game_id": game_id,
        }
        _sync_web_history_from_job(job_id, result)
        return result

    except Exception as e:
        logger.exception(f"[Job Failed] game_id={game_id}")
        result = {
            "status": "error",
            "error": str(e),
            "mat_path": src_key,
            "game_id": game_id,
        }
        _sync_web_history_from_job(job_id, result)
        return result


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
    processed = 0
    errors = 0
    total_files = len(mat_s3_keys)
    s3 = HintS3Storage.from_settings()
    original_fnames = original_fnames or []
    status_ttl = calc_batch_job_timeout(total_files) + 3600

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
                    "file_index": idx + 1,
                    "total_files": total_files,
                    "game_id": game_id,
                    "mat_path": mat_key,
                    "has_games": has_games,
                    "red_player": red_player,
                    "black_player": black_player,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
                ttl=status_ttl,
            )
            _sync_web_history_batch_file(
                job_id,
                filename=fname,
                game_id=game_id,
                red_player=red_player,
                black_player=black_player,
            )

            logger.info(
                f"[Batch File Completed] {fname} -> {mat_key} (has_games={has_games})"
            )
            processed += 1

        except Exception as e:
            logger.exception(f"[Batch File Failed] {fname}")
            publish_batch_file_ready(
                batch_id,
                idx,
                {
                    "status": "error",
                    "fname": fname,
                    "next_fname": next_fname,
                    "file_index": idx + 1,
                    "total_files": total_files,
                    "error": str(e)[:200],
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
                ttl=status_ttl,
            )
            _sync_web_history_batch_file(
                job_id,
                filename=fname,
                error=str(e)[:200],
            )
            errors += 1

        # Снижаем риск OOM / kill work-horse на длинных батчах
        gc.collect()

    # Маркер до return: если horse убьют при сериализации результата, бот всё равно завершит батч
    publish_batch_completed(batch_id, total_files, ttl=status_ttl)

    logger.info(
        f"[Batch Job Completed] batch_id={batch_id}, "
        f"ok={processed}, errors={errors}, total={total_files}"
    )
    return {
        "batch_id": batch_id,
        "total_files": total_files,
        "processed": processed,
        "errors": errors,
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
        worker_name = f"hint-{socket.gethostname()}-{os.getpid()}"
        worker = Worker(
            [queue_analysis, queue_batch],
            connection=redis_conn,
            name=worker_name,
        )
        logger.info(
            "🚀 Starting Worker '%s' on queues 'backgammon_analysis' and "
            "'backgammon_batch_analysis'...",
            worker_name,
        )
        worker.work()
    except Exception as e:
        logger.exception("Worker crashed with error")
        sys.exit(1)
