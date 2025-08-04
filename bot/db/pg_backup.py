import asyncio
import subprocess
import os
from datetime import datetime
from loguru import logger
import yadisk
from bot.config import settings
from yadisk.exceptions import YaDiskError

def new_client():
    return yadisk.AsyncClient(token=settings.YA_API_TOKEN)

async def upload_to_yandex_disk(file_path: str, file_name: str, max_retries: int = 3, retry_delay: int = 2):
    client = new_client()
    # Формируем путь: /PG_backups/dd.mm.yy_HH.MM.SS_db_backup.sql
    remote_path = f"/PG_backups/{file_name}"

    async with client:
        # Создаём корневую папку, если нет
        try:
            contents = [i async for i in client.listdir("/")]
            if not any(item["name"] == "PG_backups" for item in contents):
                await client.mkdir("/PG_backups")
                logger.info("Создано: /PG_backups")
        except YaDiskError as e:
            logger.error(f"Ошибка при проверке /PG_backups: {e}")
            raise

        # Загружаем файл
        for attempt in range(max_retries):
            try:
                await client.upload(file_path, remote_path, overwrite=True)
                logger.info(f"Файл {file_path} успешно сохранён в {remote_path} ✅")
                break
            except YaDiskError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Ошибка при загрузке после {max_retries} попыток: {e} ❌")
                    raise
                logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}. Повтор через {retry_delay} сек...")
                await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Неожиданная ошибка при загрузке: {e} ❌")
                raise

async def backup_postgres_to_yandex_disk():
    timestamp = datetime.now().strftime("%d.%m.%y_%H.%M.%S")
    backup_name = f"{timestamp}_db_backup.sql"
    temp_file_path = f"/tmp/{backup_name}"

    try:
        logger.info(f"Создаю SQL-дамп PostgreSQL: {backup_name}")

        cmd = [
            "pg_dump",
            "-h", 'db',
            "-U", settings.POSTGRES_USER,
            "-d", settings.POSTGRES_DB,
            "-f", temp_file_path
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

        process = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if process.returncode != 0:
            logger.error(f"Ошибка pg_dump: {process.stderr}")
            raise Exception("Не удалось создать дамп")

        await upload_to_yandex_disk(temp_file_path, backup_name)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

async def main():
    try:
        await backup_postgres_to_yandex_disk()
    except Exception as e:
        logger.error(f"Ошибка в main: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())