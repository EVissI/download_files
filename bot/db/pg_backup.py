import asyncio
import subprocess
import os
from datetime import datetime
from loguru import logger
import yadisk
from bot.config import settings
from yadisk.exceptions import YaDiskError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


def new_client():
    return yadisk.AsyncClient(token=settings.YA_API_TOKEN)


async def upload_to_yandex_disk(
    file_path: str, file_name: str, max_retries: int = 3, retry_delay: int = 2
):
    client = new_client()
    remote_path = f"/PG_backups/{file_name}"

    async with client:
        try:
            contents = [i async for i in client.listdir("/")]
            if not any(item["name"] == "PG_backups" for item in contents):
                await client.mkdir("/PG_backups")
                logger.info("Создана папка: /PG_backups")
        except YaDiskError as e:
            logger.error(f"Ошибка при проверке папки: {e}")
            raise

        for attempt in range(max_retries):
            try:
                await client.upload(file_path, remote_path, overwrite=True)
                logger.info(f"Файл успешно загружен в {remote_path} ✅")
                break
            except YaDiskError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Ошибка загрузки после {max_retries} попыток: {e} ❌")
                    raise
                logger.warning(f"Попытка {attempt + 1}/{max_retries} не удалась: {e}")
                await asyncio.sleep(retry_delay)
            except Exception as e:
                logger.error(f"Неожиданная ошибка загрузки: {e}")
                raise


async def backup_postgres_to_yandex_disk():
    timestamp = datetime.now().strftime("%d.%m.%y_%H.%M.%S")
    backup_name = f"{timestamp}_db_backup.sql"
    temp_file_path = f"/tmp/{backup_name}"

    try:
        logger.info(f"Создаю SQL-дамп: {backup_name}")
        cmd = [
            "docker",
            "exec",
            "db",
            "/usr/lib/postgresql/18/bin/pg_dump",
            "-h",
            "db",
            "-U",
            settings.POSTGRES_USER,
            "-d",
            settings.POSTGRES_DB,
        ]
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

        process = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if process.returncode != 0:
            logger.error(f"Ошибка pg_dump: {process.stderr}")
            raise Exception("Не удалось создать дамп")

        with open(temp_file_path, "w") as f:
            f.write(process.stdout)

        await upload_to_yandex_disk(temp_file_path, backup_name)

    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(backup_postgres_to_yandex_disk, CronTrigger(hour=0, minute=0))
    scheduler.start()

    logger.info(
        "Планировщик запущен. Резервное копирование будет выполняться каждый день в 00:00."
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
