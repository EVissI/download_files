from loguru import logger
import yadisk
import asyncio
from bot.config import settings
from yadisk.exceptions import PathExistsError, YaDiskError


def new_client():
    return yadisk.AsyncClient(token=settings.YA_API_TOKEN)


async def save_file_to_yandex_disk(
    file_path: str, file_name: str, max_retries: int = 3, retry_delay: int = 2
):
    client = new_client()
    remote_path = f"/BG_match/{file_name}"

    async with client:
        for attempt in range(max_retries):
            try:
                await client.upload(file_path, remote_path, overwrite=True)
                logger.info(f"Файл {file_path} успешно сохранён в {remote_path} ✅")
                return True

            except PathExistsError:
                logger.info(f"Файл уже существует в {remote_path}, перезаписан ✅")
                return True

            except (YaDiskError, ConnectionError, OSError) as e:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Ошибка при сохранении после {max_retries} попыток: {e} ❌"
                    )
                    raise

                logger.warning(
                    f"Попытка {attempt + 1}/{max_retries} не удалась: {e}. Повторная попытка через {retry_delay} сек..."
                )
                await asyncio.sleep(retry_delay)

            except Exception as e:
                logger.error(f"Неожиданная ошибка при сохранении: {e} ❌")
