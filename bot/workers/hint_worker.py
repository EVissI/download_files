import os
import sys
import logging
from redis import Redis  # ✅ Правильный импорт
from rq import Worker, Queue  # ✅ БЕЗ Connection
from bot.common.func.hint_viewer import process_mat_file

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ✅ Подключение к Redis с ACL-пользователем
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Два варианта подключения:
# 1. Если используешь ACL-пользователя
REDIS_USER = os.getenv('REDIS_USER')
REDIS_USER_PASSWORD = os.getenv('REDIS_USER_PASSWORD')

# 2. Если используешь default пароль
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')

# Выбираем какой использовать
if REDIS_USER and REDIS_USER_PASSWORD:
    # С ACL-пользователем
    redis_url = f'redis://{REDIS_USER}:{REDIS_USER_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    logger.info(f"Connecting to Redis with ACL user: {REDIS_USER}")
else:
    # С default пользователем (только пароль)
    redis_url = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
    logger.info(f"Connecting to Redis with default user")

logger.info(f"Redis URL: redis://<user>:<pass>@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

redis_conn = Redis.from_url(redis_url, decode_responses=False)


logger.info(f"Worker started in: {os.getcwd()}")
logger.info(f"Files directory: {os.path.abspath('files')}")
logger.info(f"Contents of files/: {os.listdir('files') if os.path.exists('files') else 'NOT EXISTS'}")

def analyze_backgammon_job(mat_path: str, json_path: str, user_id: str, job_id: str = None):
    """
    Анализирует один .mat файл (запускается в worker-е).
    """
    # ✅ Добавить детальное логирование путей
    abs_mat_path = os.path.abspath(mat_path)
    abs_json_path = os.path.abspath(json_path)
    
    logger.info(f"[Job Start] job_id={job_id}")
    logger.info(f"Original mat_path: {mat_path}")
    logger.info(f"Absolute mat_path: {abs_mat_path}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Exists? {os.path.exists(abs_mat_path)}")
    
    if os.path.exists(abs_mat_path):
        logger.info(f"File size: {os.path.getsize(abs_mat_path)} bytes")
    else:
        logger.error(f"File NOT FOUND: {abs_mat_path}")
        # Попробуем найти в текущей директории
        alternative_path = os.path.join(os.getcwd(), mat_path)
        logger.info(f"Trying alternative path: {alternative_path}")
        logger.info(f"Alternative exists? {os.path.exists(alternative_path)}")
    
    try:
        if not os.path.exists(abs_mat_path):
            raise FileNotFoundError(f"Файл не найден: {abs_mat_path}")
        
        process_mat_file(abs_mat_path, abs_json_path, user_id)
        
        games_dir = abs_json_path.rsplit(".", 1)[0] + "_games"
        has_games = os.path.exists(games_dir) and any(
            f.endswith(".json") for f in os.listdir(games_dir)
        )
        
        logger.info(f"[Job Success] {abs_mat_path} -> {abs_json_path}")
        return {"status": "success", "mat_path": abs_mat_path, "has_games": has_games}
    
    except Exception as e:
        logger.exception(f"[Job Failed] {abs_mat_path}")
        return {"status": "error", "error": str(e), "mat_path": abs_mat_path}

if __name__ == '__main__':
    # ✅ Установить явную рабочую директорию
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(os.path.dirname(script_dir))
    os.chdir(project_dir)
    logger.info(f"Working directory set to: {os.getcwd()}")
    
    # Проверка подключения к Redis
    try:
        redis_conn.ping()
        logger.info(f"✅ Connected to Redis")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        sys.exit(1)
    
    try:
        queue = Queue('backgammon_analysis', connection=redis_conn)
        worker = Worker([queue], connection=redis_conn)
        logger.info(f"🚀 Starting Worker...")
        worker.work()
    except Exception as e:
        logger.exception("Worker crashed")
        sys.exit(1)