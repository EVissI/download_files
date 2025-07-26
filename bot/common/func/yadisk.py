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
    client = new_client()  # Замените на вашу реализацию new_client()
    # Разбиваем file_name на компоненты
    date_part, players_part = file_name.split(":", 1)
    date_folder = date_part.split("-")[0]  # Берем только dd.mm.yy
    time_part = date_part.split("-")[1]  # Берем только HH.MM.SS
    players = players_part.replace(".mat", "")  # Оба игрока player1:player2
    players = players.split(":") 
    time_file = f"{time_part}:{players}"  # HH.MM.SS:player1:player2

    # Формируем полный путь


    async with client:
        base_path = "/BG_match"
        # Проверяем и создаем папку /BG_match/{players}
        for player in players:
            players_path = f"{base_path}/{player}"
            date_path = f"{players_path}/{date_folder}"
            remote_path = f"{date_path}/{time_file}.mat"
            try:
                contents = [i async for i in client.listdir(base_path)]
                if not any(item["name"] == players for item in contents):
                    await client.mkdir(players_path)
                    logger.info(f"Создано: {players_path}")
            except yadisk.YaDiskError as e:
                logger.error(f"Ошибка при проверке {base_path}: {e}")
                raise

            # Проверяем и создаем папку /BG_match/{players}/{date_folder}
            try:
                contents = [i async for i in client.listdir(players_path)]
                if not any(item["name"] == date_folder for item in contents):
                    await client.mkdir(date_path)
                    logger.info(f"Создано: {date_path}")
            except yadisk.YaDiskError as e:
                logger.error(f"Ошибка при проверке {players_path}: {e}")
                raise

            for attempt in range(max_retries):
                try:
                    await client.upload(file_path, remote_path, overwrite=True)
                    logger.info(f"Файл {file_path} успешно сохранён в {remote_path} ✅")
                    return True

                except yadisk.PathExistsError:
                    logger.info(f"Файл уже существует в {remote_path}, перезаписан ✅")
                    return True

                except (yadisk.YaDiskError, ConnectionError, OSError) as e:
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
