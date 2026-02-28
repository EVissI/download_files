import asyncio
import os
import aiohttp
from loguru import logger
from bot.config import settings


class SyncthingSync:
    """Управление синхронизацией Syncthing"""

    def __init__(self):
        self.api_key = settings.SYNCTHING_API_KEY
        self.host = settings.SYNCTHING_HOST
        self.folder_id = settings.SYNCTHING_FOLDER

        if not self.api_key:
            logger.warning("⚠️ SYNCTHING_API_KEY не установлен!")

        self.headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}
        self.base_url = f"http://{self.host}/rest"

    async def trigger_scan(self) -> bool:
        """
        Запустить db/scan на отправителе (бот) — Syncthing сразу заметит новый файл.
        Вызывать после сохранения файла, до постановки задачи в очередь.
        """
        if not self.api_key:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/db/scan",
                    params={"folder": self.folder_id},
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        logger.debug("Syncthing scan triggered")
                        return True
                    logger.warning(f"Syncthing scan failed: {resp.status}")
                    return False
        except Exception as e:
            logger.warning(f"Syncthing trigger_scan: {e}")
            return False

    async def wait_for_file_sync(self, file_path: str, max_wait: int = 120) -> bool:
        """
        Ожидание появления файла на диске после синхронизации Syncthing.

        Использует polling — надёжно работает когда воркер в Docker и не может
        достучаться до Syncthing API (localhost:8384). Events API (ItemFinished)
        не подходит для приёмника в отдельном контейнере.

        Документация: https://docs.syncthing.net/events/itemfinished.html
        """
        return await self.wait_for_file(file_path, max_wait)


    async def _verify_file(self, file_path: str) -> bool:
        """Проверить, что файл существует, не пустой и читаемый."""
        if not os.path.exists(file_path):
            return False
        try:
            size = os.path.getsize(file_path)
            if size == 0:
                return False
            with open(file_path, "rb") as f:
                f.read(1)  # проверка чтения
            logger.debug(f"Файл проверен: {file_path} ({size} bytes)")
            return True
        except Exception:
            return False

    async def sync_and_wait(self, max_wait=30) -> bool:
        """
        Запустить scan и ждать, пока локальное устройство синхронизировано (needBytes=0).
        Важно: на отправителе needBytes=0 сразу — этот метод надёжен только на приёмнике.
        """
        if not self.api_key:
            logger.warning("⚠️ Syncthing API ключ не установлен")
            return True

        try:
            logger.info("🔄 Синхронизирую файлы Syncthing...")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/db/scan",
                    params={"folder": self.folder_id},
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status != 200:
                        logger.warning(f"⚠️ Ошибка пересканирования: {response.status}")
                        return False

                start_time = asyncio.get_running_loop().time()
                stable_count = 0  # нужны 2 подряд idle+needBytes=0 для устойчивости

                while asyncio.get_running_loop().time() - start_time < max_wait:
                    async with session.get(
                        f"{self.base_url}/db/status",
                        params={"folder": self.folder_id},
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as status_response:
                        status = await status_response.json()
                        state = status.get("state")
                        need_bytes = status.get("needBytes", 0)

                        if state == "idle" and need_bytes == 0:
                            stable_count += 1
                            if stable_count >= 2:
                                logger.info("✅ Синхронизация завершена (db/status)")
                                return True
                        else:
                            stable_count = 0

                    await asyncio.sleep(0.5)

                logger.warning(f"⚠️ Timeout sync_and_wait (max_wait={max_wait}s)")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка Syncthing: {e}")
            return False

    async def wait_for_file(self, file_path: str, max_wait: int = 120) -> bool:
        """Ждать появления файла на диске. Проверяет существование и читаемость."""
        loop = asyncio.get_running_loop()
        start_time = loop.time()
        check_interval = 0.5

        while loop.time() - start_time < max_wait:
            if await self._verify_file(file_path):
                logger.info(f"✅ Файл найден: {file_path}")
                return True
            await asyncio.sleep(check_interval)

        abs_path = os.path.abspath(file_path)
        logger.error(
            f"❌ Файл не найден после ожидания {max_wait}s: {file_path} | "
            f"абс. путь: {abs_path} | CWD: {os.getcwd()}"
        )
        return False
