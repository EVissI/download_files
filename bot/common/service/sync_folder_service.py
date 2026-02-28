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

    def _file_matches_item(self, file_path: str, item: str) -> bool:
        """Проверяет, соответствует ли item из Syncthing нашему file_path."""
        basename = os.path.basename(file_path)
        # item в Syncthing — путь относительно корня папки (например "xxx.mat" или "files/xxx.mat")
        return item == basename or item.endswith("/" + basename) or item == file_path

    async def _get_last_event_id(self, session: aiohttp.ClientSession) -> int:
        """Получить ID последнего события."""
        async with session.get(
            f"{self.base_url}/events",
            params={"limit": 1},
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=5),
        ) as resp:
            if resp.status != 200:
                return 0
            events = await resp.json()
            return events[-1]["id"] if events else 0

    async def wait_for_file_sync(self, file_path: str, max_wait: int = 60) -> bool:
        """
        Надёжное ожидание синхронизации файла.
        Использует Events API (ItemFinished) + проверку файла на диске.
        Без произвольных sleep — только event-driven ожидание и polling файла.
        """
        if not self.api_key:
            logger.warning("⚠️ Syncthing API ключ не установлен")
            return await self.wait_for_file(file_path, max_wait)

        basename = os.path.basename(file_path)
        start_time = asyncio.get_event_loop().time()

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Запустить пересканирование (отправитель обнаружит новый файл)
                async with session.post(
                    f"{self.base_url}/db/scan",
                    params={"folder": self.folder_id},
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"⚠️ Ошибка scan: {response.status}, fallback на wait_for_file"
                        )
                        return await self.wait_for_file(file_path, max_wait)

                # 2. Получить текущий event ID
                last_id = await self._get_last_event_id(session)

                # 3. Ждём: либо ItemFinished для нашего файла, либо файл появился на диске
                while asyncio.get_event_loop().time() - start_time < max_wait:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    timeout_sec = min(30, int(max_wait - elapsed), 30)
                    if timeout_sec <= 0:
                        break

                    # Long-poll Events API (блокируется до события или timeout)
                    try:
                        async with session.get(
                            f"{self.base_url}/events",
                            params={
                                "events": "ItemFinished",
                                "since": last_id,
                                "timeout": timeout_sec,
                            },
                            headers=self.headers,
                            timeout=aiohttp.ClientTimeout(total=timeout_sec + 5),
                        ) as events_resp:
                            if events_resp.status != 200:
                                break

                            events = await events_resp.json()
                            for ev in events:
                                last_id = ev["id"]
                                if ev.get("type") != "ItemFinished":
                                    continue
                                data = ev.get("data") or {}
                                item = data.get("item", "")
                                err = data.get("error")

                                if err:
                                    logger.warning(
                                        f"ItemFinished с ошибкой: {item} — {err}"
                                    )
                                    continue
                                if self._file_matches_item(file_path, item):
                                    if await self._verify_file(file_path):
                                        logger.info(
                                            f"✅ Синхронизация подтверждена (ItemFinished): {item}"
                                        )
                                        return True
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        logger.debug(f"Events API: {e}")

                    # Проверяем файл на диске (основная гарантия)
                    if await self._verify_file(file_path):
                        logger.info(f"✅ Файл синхронизирован: {file_path}")
                        return True

                # 4. Fallback: финальная проверка файла
                remaining = max(
                    5, int(max_wait - (asyncio.get_event_loop().time() - start_time))
                )
                return await self._verify_file(file_path) or await self.wait_for_file(
                    file_path, remaining
                )

        except Exception as e:
            logger.error(f"❌ wait_for_file_sync: {e}")
            return await self.wait_for_file(file_path, max_wait)

        return False

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

                start_time = asyncio.get_event_loop().time()
                stable_count = 0  # нужны 2 подряд idle+needBytes=0 для устойчивости

                while asyncio.get_event_loop().time() - start_time < max_wait:
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

    async def wait_for_file(self, file_path: str, max_wait: int = 30) -> bool:
        """Ждать появления файла на диске. Проверяет существование и читаемость."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < max_wait:
            if await self._verify_file(file_path):
                return True
            await asyncio.sleep(0.2)

        logger.error(f"❌ Файл не найден после ожидания: {file_path}")
        return False
