from loguru import logger
import yadisk
import asyncio
import os
import re
from datetime import datetime
import pytz
from bot.config import settings
from yadisk.exceptions import PathExistsError, YaDiskError


def new_client():
    return yadisk.AsyncClient(token=settings.YA_API_TOKEN)


_EXPECTED_NAME = re.compile(
    r"^(?P<date>\d{2}\.\d{2}\.\d{2})-(?P<time>\d{2}\.\d{2}\.\d{2}):(?P<players>.+)$"
)


def _parse_yadisk_file_name(file_name: str) -> tuple[str, str, list[str]]:
    """
    Ожидаемый формат: dd.mm.yy-HH.MM.SS:игрок1:игрок2.mat
    Возвращает (date_folder, time_file, players).
    """
    base = os.path.basename(file_name)
    match = _EXPECTED_NAME.match(base)
    if match:
        date_folder = match.group("date")
        time_part = match.group("time")
        players_part = match.group("players")
        players = players_part.replace(".mat", "").split(":")
        players = [p for p in players if p]
        time_file = f"{time_part}:{players_part.replace('.mat', '')}"
        if players:
            return date_folder, time_file, players

    # Fallback: исходное имя без ожидаемого формата (например original.mat)
    moscow_tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(moscow_tz)
    date_folder = now.strftime("%d.%m.%y")
    time_part = now.strftime("%H.%M.%S")
    stem = os.path.splitext(base)[0] or "unknown"
    safe_stem = re.sub(r'[\\/:*?"<>|]', "_", stem)
    time_file = f"{time_part}:{safe_stem}"
    logger.warning(
        f"Имя файла не в формате date:players ({base!r}), "
        f"сохраняем в папку _unsorted"
    )
    return date_folder, time_file, ["_unsorted"]


async def save_file_to_yandex_disk(
    file_path: str, file_name: str, max_retries: int = 3, retry_delay: int = 2
):
    try:
        date_folder, time_file, players = _parse_yadisk_file_name(file_name)
        client = new_client()

        async with client:
            base_path = "/BG_match"
            for player in players:
                players_path = f"{base_path}/{player}"
                date_path = f"{players_path}/{date_folder}"
                remote_path = f"{date_path}/{time_file}.mat"

                # Создаём папку игрока, если нет
                try:
                    contents = [i async for i in client.listdir(base_path)]
                    if not any(item["name"] == player for item in contents):
                        await client.mkdir(players_path)
                        logger.info(f"Создано: {players_path}")
                except YaDiskError as e:
                    logger.error(f"Ошибка при проверке {base_path}: {e}")
                    raise

                # Создаём папку даты, если нет
                try:
                    contents = [i async for i in client.listdir(players_path)]
                    if not any(item["name"] == date_folder for item in contents):
                        await client.mkdir(date_path)
                        logger.info(f"Создано: {date_path}")
                except YaDiskError as e:
                    logger.error(f"Ошибка при проверке {players_path}: {e}")
                    raise

                # Загружаем файл
                for attempt in range(max_retries):
                    try:
                        await client.upload(file_path, remote_path, overwrite=True)
                        logger.info(
                            f"Файл {file_path} успешно сохранён в {remote_path} ✅"
                        )
                        break
                    except PathExistsError:
                        logger.info(
                            f"Файл уже существует в {remote_path}, перезаписан ✅"
                        )
                        break
                    except (YaDiskError, ConnectionError, OSError) as e:
                        if attempt == max_retries - 1:
                            logger.error(
                                f"Ошибка при сохранении после {max_retries} попыток: {e} ❌"
                            )
                            raise
                        logger.warning(
                            f"Попытка {attempt + 1}/{max_retries} не удалась: {e}. "
                            f"Повторная попытка через {retry_delay} сек..."
                        )
                        await asyncio.sleep(retry_delay)
                    except Exception as e:
                        logger.error(f"Неожиданная ошибка при сохранении: {e} ❌")
                        raise
    except Exception as e:
        logger.exception(
            f"Не удалось сохранить файл на Яндекс.Диск "
            f"(path={file_path!r}, name={file_name!r}): {e}"
        )
