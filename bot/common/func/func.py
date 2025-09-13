import prettytable as pt
from io import BytesIO
import os
import re
from PIL import Image, ImageEnhance, ImageFilter

from loguru import logger
import pytesseract

from bot.config import translator_hub
from typing import TYPE_CHECKING
from fluentogram import TranslatorRunner

from bot.db.models import User

if TYPE_CHECKING:
    from locales.stub import TranslatorRunner


def get_user_file_name(user_id: int, original_name: str, files_dir: str) -> str:
    """
    Генерирует уникальное имя файла для пользователя в формате {user_id}_fileN.ext,
    где N — порядковый номер файла пользователя.
    """
    base, ext = os.path.splitext(original_name)
    n = 1
    while True:
        new_name = f"{user_id}_file{n}{ext}"
        new_path = os.path.join(files_dir, new_name)
        if not os.path.exists(new_path):
            return new_name
        n += 1


def preprocess_image(image_bytes: bytes) -> Image:
    image = Image.open(BytesIO(image_bytes))

    # Увеличение размера изображения
    image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)

    # Преобразование в чёрно-белое
    image = image.convert("L")

    # Увеличение контраста
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)

    # Удаление шума
    image = image.filter(ImageFilter.MedianFilter())

    return image


def extract_eg_summary(image_bytes: bytes) -> dict:
    """
    Извлекает основные показатели анализа из скриншота GNUBG с динамическими никнеймами.
    Ключи словаря — никнеймы игроков, значения — словарь с их показателями.
    Если параметр не удалось извлечь, он получает значение 'нет'.
    """
    image = preprocess_image(image_bytes)
    text = pytesseract.image_to_string(image, lang="rus+eng", config="--psm 4 --oem 1")
    logger.info(f"Извлеченный текст из изображения:\n{text}")
    result = {}

    lines = text.splitlines()
    nicknames_match = None

    for line in lines:
        if "Анализ хода" in line or "Сводка" in line or not line.strip():
            continue

        nicknames_match = re.match(r"^([^\s]+)\s+([^\s]+)$", line.strip())
        if nicknames_match:
            break

    if not nicknames_match:
        return {"error": "Не удалось найти никнеймы игроков"}

    nick1, nick2 = nicknames_match.group(1), nicknames_match.group(2)

    result[nick1] = {}
    result[nick2] = {}

    for line in lines:
        match = re.search(
            r"(\d+|нет)\s*(?:\((\d+|нет)\))?\s*Ошибок\s*\(Зевков\)\s*(\d+|нет)(?:\s*\((\d+|нет)\))?",
            line,
        )
        if match:
            result[nick1]["error"] = parse_eg_value(match.group(1))
            result[nick1]["errors_extra"] = parse_eg_value(match.group(2))
            result[nick2]["errors"] = parse_eg_value(match.group(3))
            result[nick2]["errors_extra"] = parse_eg_value(match.group(4))
            break

    for line in lines:
        match = re.search(
            r"(\d+|нет)\s*(?:\((\d+|нет)\))?\s*Ошибок удвоений\s*\(Зевков\)\s*(\d+|нет)(?:\s*\((\d+|нет)\))?",
            line,
        )
        if match:
            result[nick1]["doubling"] = parse_eg_value(match.group(1))
            result[nick1]["doubling_extra"] = parse_eg_value(match.group(2))
            result[nick2]["doubling"] = parse_eg_value(match.group(3))
            result[nick2]["doubling_extra"] = parse_eg_value(match.group(4))
            break

    for line in lines:
        match = re.search(
            r"(\d+|нет)\s*(?:\((\d+|нет)\))?\s*Ошибок взятий\s*\(Зевков\)\s*(\d+|нет)(?:\s*\((\d+|нет)\))?",
            line,
        )
        if match:
            result[nick1]["taking"] = parse_eg_value(match.group(1))
            result[nick1]["taking_extra"] = parse_eg_value(match.group(2))
            result[nick2]["taking"] = parse_eg_value(match.group(3))
            result[nick2]["taking_extra"] = parse_eg_value(match.group(4))
            break

    for line in lines:
        match = re.search(
            r"([-+]?\d+,\d+)(?:\s*\((\d+)\))?\s*Удача\s*\(Джокер\)\s*([-+]?\d+,\d+)(?:\s*\((\d+)\))?",
            line,
        )
        if match:
            result[nick1]["luck"] = parse_eg_value(match.group(1), as_int=False)
            result[nick1]["luck_extra"] = parse_eg_value(match.group(2))
            result[nick2]["luck"] = parse_eg_value(match.group(3), as_int=False)
            result[nick2]["luck_extra"] = parse_eg_value(match.group(4))
            break

    for line in lines:
        match = re.search(
            r"([-+]?\d+,\d+)\s*Качество игры\s*\(PR\)\s*([-+]?\d+,\d+)", line
        )
        if match:
            result[nick1]["quality"] = float(match.group(1).replace(",", "."))
            result[nick2]["quality"] = float(match.group(2).replace(",", "."))
            break

    return result


def determine_rank(pr: float, i18n: TranslatorRunner) -> str:
    """
    Определяет ранг пользователя на основе значения PR и локализации.
    :param pr: Performance Rating (PR)
    :param i18n: TranslatorRunner для локализации
    :return: Локализованный ранг пользователя
    """
    pr = abs(pr)
    if pr < 2.5:
        return i18n.user.rank.superchamp()
    elif pr < 4.0:
        return i18n.user.rank.champ()
    elif pr < 6.0:
        return i18n.user.rank.expert()
    elif pr < 8.0:
        return i18n.user.rank.advanced()
    elif pr < 10.0:
        return i18n.user.rank.intermediate()
    elif pr < 15.0:
        return i18n.user.rank.casual()
    else:
        return i18n.user.rank.beginner()


def determine_rank_rate_chequer(deviation: float) -> str:
    """
    Определяет рейтинг броска на основе отклонения эквити от среднего значения.
    :param deviation: Отклонение эквити от среднего (float)
    :return: Рейтинг броска ("very lucky", "lucky", "unmarked", "unlucky", "very unlucky")
    """
    if deviation > 0.6:
        return "very lucky"
    elif deviation > 0.3:
        return "lucky"
    elif deviation > -0.3:
        return "unmarked"
    elif deviation > -0.6:
        return "unlucky"
    else:
        return "very unlucky"
    
def normalize_slashes(text: str | None) -> str | None:
    """
    Заменяет все обратные слеши '\' на прямые '/'.
    Возвращает None как есть.
    """
    if text is None:
        return None
    return text.replace("\\", "/")

def get_analysis_data(analysis_data: dict, selected_player: str = None) -> dict:
    """
    Если передан selected_player — возвращает словарь только по нему.
    Если не передан — возвращает словарь по всем игрокам (ключи — имена игроков).
    """
    logger.info(analysis_data)
    def extract(player):
        chequer = analysis_data.get("chequerplay", {}).get(player, {})
        luck = analysis_data.get("luck", {}).get(player, {})
        cube = analysis_data.get("cube", {}).get(player, {})
        overall = analysis_data.get("overall", {}).get(player, {})
        luck_rate = 0
        if luck.get("luck_rate_memg_points") is not None:
            luck_rate = luck.get("luck_rate_memg_points")
        elif luck.get("luck_rate_memg_mwc_points") is not None:
            luck_rate = luck.get("luck_rate_memg_mwc_points")

        error_rate = 0
        if chequer.get("error_rate_memg_points") is not None:
            error_rate = format_value(chequer.get("error_rate_memg_points"), True)
        elif chequer.get("error_rate_memg_mwc_points") is not None:
            error_rate = format_value(chequer.get("error_rate_memg_mwc_points"), True)

        def get_cube_param(name):
            # Возможные суффиксы для поиска
            suffixes = [
                "_emg_mwc_points",
                "_emg_points",
                "_mwc_points",
                "_memg_points",
                "_memg_mwc_points",
                "_memg",
                "_memg_mwc",
                "_memg_emg_points",
                "_emg_mwc",
                "_emg",
                "_mwc",
                "_points",
                "",
            ]
            for suffix in suffixes:
                val = cube.get(f"{name}{suffix}")
                if val is not None:
                    try:
                        # Пробуем определить тип данных
                        if isinstance(val, (int, float)):
                            return val  # Возвращаем как есть, если уже число
                        elif isinstance(val, str):
                            # Пробуем преобразовать строку в число
                            if val.isdigit():
                                return int(val)  # Целое число
                            try:
                                return float(val)  # Число с плавающей точкой
                            except ValueError:
                                logger.warning(f"Value {val} for {name}{suffix} is a string but not a number, returning as is")
                                return val  # Возвращаем строку, если не число
                        else:
                            logger.warning(f"Unexpected type for {name}{suffix}={val}, returning 0")
                            return 0
                    except Exception as e:
                        logger.warning(f"Error processing {name}{suffix}={val}: {e}, returning 0")
                        return 0
            logger.warning(f"No valid value found for {name} with any suffix, returning 0")
            return 0
        
        return {
            # Chequerplay data
            "moves_marked_bad": int(chequer.get("moves_marked_bad", 0)),
            "moves_marked_very_bad": int(chequer.get("moves_marked_very_bad", 0)),
            "error_rate_chequer": float(error_rate),
            "chequerplay_rating": str(chequer.get("chequerplay_rating", "Нет данных")),
            # Luck data
            "rolls_marked_very_lucky": int(luck.get("rolls_marked_very_lucky", 0)),
            "rolls_marked_lucky": int(luck.get("rolls_marked_lucky", 0)),
            "rolls_marked_unlucky": int(luck.get("rolls_marked_unlucky", 0)),
            "rolls_marked_very_unlucky": int(luck.get("rolls_marked_very_unlucky", 0)),
            "rolls_rate_chequer": float(luck_rate),
            "luck_rating": str(luck.get("luck_rating", "Нет данных")),
            # Cube data
            "missed_doubles_below_cp": get_cube_param("missed_doubles_below_cp"),
            "missed_doubles_above_cp": get_cube_param("missed_doubles_above_cp"),
            "wrong_doubles_below_sp": get_cube_param("wrong_doubles_below_dp"),  
            "wrong_doubles_above_tg": get_cube_param("wrong_doubles_above_tg"),
            "wrong_takes": get_cube_param("wrong_takes"),
            "wrong_passes": get_cube_param("wrong_passes"),
            "cube_error_rate": get_cube_param("error_rate"),
            "cube_decision_rating": str(cube.get("cube_decision_rating", "Нет данных")),
            # Overall data
            "snowie_error_rate": float(overall.get("snowie_error_rate", 0)),
            "overall_rating": str(overall.get("overall_rating", "Нет данных")),
        }

    if selected_player is not None:
        return extract(selected_player)
    else:
        players = list(analysis_data.get("chequerplay", {}).keys())
        return {player: extract(player) for player in players}

def create_message_for_user(user: User) -> str:
    return (
        f"ID: {user.id}\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Имя: {user.first_name or 'нет'}\n"
        f"Фамилия: {user.last_name or 'нет'}\n"
        f"Роль: {user.role}\n"
        f"Язык: {user.lang_code or 'не установлен'}\n"
        f"Поставленное имя: {user.admin_insert_name or 'не установлен'}"
    )
def format_detailed_analysis(analysis_data: dict, i18n: TranslatorRunner) -> str:
    """
    Форматирует результаты анализа для двух игроков в виде ASCII-таблиц для вывода в Telegram,
    используя уже отформатированный словарь из get_analysis_data.
    """
    try:
        logger.info(analysis_data)
        player_names = list(analysis_data.keys())
        if len(player_names) != 2:
            raise ValueError("No data found for two players")

        player1_name, player2_name = player_names
        p1 = analysis_data[player1_name]
        p2 = analysis_data[player2_name]
        max_length = 10

        # Словарь для сокращения рейтингов
        rating_shortcuts = {
            "Advanced": "Advanced",
            "Supernatural": "Supernat",
            "Expert": "Expert",
            "World class": "WorldClass",
            "None": "None",
            "Good dice, man!": "GoodDice",
            "Bad dice, man!": "BadDice",
            "Go to Las Vegas": "SuperDice",
            "Beginner": "Beginner",
            "Intermediate": "Intermed",
            "Casual player": "Casual",
            "Master": "Mastrer",
            "Professional": "Pro",
            "Grandmaster": "GrandMstr",
            "No data": "N/A",
        }

        def format_value(val, is_float=False, max_length=max_length):
            if val is None or val == "No data":
                return "N/A".ljust(max_length)[:max_length]
            cleaned_val = re.sub(r"\s*\(.*\)", "", str(val)).strip()
            if is_float and cleaned_val:
                try:
                    num = float(cleaned_val)
                    formatted = f"{num:.1f}"
                    if num > 0:
                        formatted = f"+{formatted}"
                    return (formatted + " " * max_length)[:max_length]
                except ValueError:
                    return cleaned_val.ljust(max_length)[:max_length]
            return rating_shortcuts.get(cleaned_val, cleaned_val).ljust(max_length)[
                :max_length
            ]

        # Таблица для Chequerplay
        chequerplay_table = pt.PrettyTable()
        chequerplay_table.field_names = ["Param", player1_name, player2_name]
        chequerplay_table.max_width["Param"] = 15
        chequerplay_table.max_width[player1_name] = 15
        chequerplay_table.max_width[player2_name] = 15
        chequerplay_table.add_row(
            [
                i18n.analysis.chequerplay.bad_move(),
                format_value(p1["moves_marked_bad"]),
                format_value(p2["moves_marked_bad"]),
            ]
        )
        chequerplay_table.add_row(
            [
                i18n.analysis.chequerplay.bad_plus_move(),
                format_value(p1["moves_marked_very_bad"]),
                format_value(p2["moves_marked_very_bad"]),
            ]
        )
        chequerplay_table.add_row(
            [
                i18n.analysis.chequerplay.error_rate(),
                format_value(p1["error_rate_chequer"], True),
                format_value(p2["error_rate_chequer"], True),
            ]
        )
        chequerplay_table.add_row(
            [
                i18n.analysis.chequerplay.rating(),
                format_value(p1["chequerplay_rating"]),
                format_value(p2["chequerplay_rating"]),
            ]
        )

        # Таблица для Luck
        luck_table = pt.PrettyTable()
        luck_table.field_names = [i18n.analysis.param(), player1_name, player2_name]
        luck_table.max_width[i18n.analysis.param()] = 15
        luck_table.max_width[player1_name] = 15
        luck_table.max_width[player2_name] = 15
        luck_table.add_row(
            [
                i18n.analysis.luck.luck_plus_move(),
                format_value(p1["rolls_marked_very_lucky"]),
                format_value(p2["rolls_marked_very_lucky"]),
            ]
        )
        luck_table.add_row(
            [
                i18n.analysis.luck.luck_move(),
                format_value(p1["rolls_marked_lucky"]),
                format_value(p2["rolls_marked_lucky"]),
            ]
        )
        luck_table.add_row(
            [
                i18n.analysis.luck.unluck_plus_move(),
                format_value(p1["rolls_marked_very_unlucky"]),
                format_value(p2["rolls_marked_very_unlucky"]),
            ]
        )
        luck_table.add_row(
            [
                i18n.analysis.luck.unluck_move(),
                format_value(p1["rolls_marked_unlucky"]),
                format_value(p2["rolls_marked_unlucky"]),
            ]
        )
        luck_table.add_row(
            [
                i18n.analysis.luck.luck_rate(),
                format_value(p1["rolls_rate_chequer"], True),
                format_value(p2["rolls_rate_chequer"], True),
            ]
        )
        luck_table.add_row(
            [
                i18n.analysis.luck.rating(),
                format_value(p1["luck_rating"]),
                format_value(p2["luck_rating"]),
            ]
        )

        # Таблица для Cube (добавьте остальные параметры по аналогии)
        cube_table = pt.PrettyTable()
        cube_table.field_names = [i18n.analysis.param(), player1_name, player2_name]
        cube_table.max_width[i18n.analysis.param()] = 15
        cube_table.max_width[player1_name] = 15
        cube_table.max_width[player2_name] = 15
        cube_table.add_row(
            [
                i18n.analysis.cube.missed_doubles_below_cp(),
                format_value(p1["missed_doubles_below_cp"]),
                format_value(p2["missed_doubles_below_cp"]),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.missed_doubles_above_cp(),
                format_value(p1["missed_doubles_above_cp"]),
                format_value(p2["missed_doubles_above_cp"]),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.wrong_doubles_below_sp(),
                format_value(p1["wrong_doubles_below_sp"]),
                format_value(p2["wrong_doubles_below_sp"]),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.wrong_doubles_above_tg(),
                format_value(p1["wrong_doubles_above_tg"]),
                format_value(p2["wrong_doubles_above_tg"]),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.wrong_takes(),
                format_value(p1["wrong_takes"]),
                format_value(p2["wrong_takes"]),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.wrong_passes(),
                format_value(p1["wrong_passes"]),
                format_value(p2["wrong_passes"]),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.error_rate(),
                format_value(p1["cube_error_rate"], True),
                format_value(p2["cube_error_rate"], True),
            ]
        )
        cube_table.add_row(
            [
                i18n.analysis.cube.rating(),
                format_value(p1["cube_decision_rating"]),
                format_value(p2["cube_decision_rating"]),
            ]
        )

        # Таблица для Overall
        overall_table = pt.PrettyTable()
        overall_table.field_names = [i18n.analysis.param(), player1_name, player2_name]
        overall_table.max_width[i18n.analysis.param()] = 15
        overall_table.max_width[player1_name] = 15
        overall_table.max_width[player2_name] = 15
        overall_table.add_row(
            [
                i18n.analysis.overall.error_rate(),
                format_value(p1["snowie_error_rate"], True),
                format_value(p2["snowie_error_rate"], True),
            ]
        )
        overall_table.add_row(
            [
                i18n.analysis.overall.rating(),
                format_value(p1["overall_rating"]),
                format_value(p2["overall_rating"]),
            ]
        )

        # Формирование финального сообщения
        result = (
            f"📊 <b>{i18n.analysis.results()}</b>\n\n"
            f"<b>{i18n.analysis.vs(player1_name=player1_name, player2_name=player2_name)}</b>\n\n"
            f"⚪️⚫️<b>{i18n.analysis.playing_checkers()}</b>\n"
            f"<pre>{chequerplay_table.get_string()}</pre>\n\n"
            f"🎯 <b>{i18n.analysis.luck()}</b>\n"
            f"<pre>{luck_table.get_string()}</pre>\n\n"
            f"🎲 <b>{i18n.analysis.cube()}</b>\n"
            f"<pre>{cube_table.get_string()}</pre>\n\n"
            f"📈 <b>{i18n.analysis.overall_statistic()}</b>\n"
            f"<pre>{overall_table.get_string()}</pre>"
        )
        return result

    except Exception as e:
        logger.error(f"Ошибка при форматировании анализа: {e}")
        return i18n.analysis.error_formatting()


def parse_eg_value(value: str | None, as_int: bool = True) -> int | float | str:
    """
    Парсит значение из текста анализа.

    Args:
        value: Значение для парсинга
        as_int: Преобразовывать ли в целое число

    Returns:
        int | float | str: Распарсенное значение или "нет"
    """
    if not value or value.lower() == "No":
        return "No"
    try:
        if "," in value:
            return float(value.replace(",", "."))
        return int(value) if as_int else float(value)
    except (ValueError, AttributeError):
        return "No"


def format_value(value: str | float | int, is_float: bool = False) -> str:
    """Форматирует значение для вывода."""
    if value == "No":
        return "No"
    try:
        return f"{float(value):.2f}" if is_float else str(value)
    except (ValueError, TypeError):
        return str(value)


def split_message(msg: str, *, with_photo: bool) -> list[str]:
    """Split the text into parts considering Telegram limits."""
    parts = []
    while msg:
        # Determine the maximum message length based on
        # with_photo and whether it's the first iteration
        # (photo is sent only with the first message).
        if parts:
            max_msg_length = 4096
        elif with_photo:
            max_msg_length = 1024
        else:
            max_msg_length = 4096

        if len(msg) <= max_msg_length:
            # The message length fits within the maximum allowed.
            parts.append(msg)
            break

        # Cut a part of the message with the maximum length from msg
        # and find a position for a break by a newline character.
        part = msg[:max_msg_length]
        first_ln = part.rfind("\n")

        if first_ln != -1:
            # Newline character found.
            # Split the message by it, excluding the character itself.
            new_part = part[:first_ln]
            parts.append(new_part)

            # Trim msg to the length of the new part
            # and remove the newline character.
            msg = msg[first_ln + 1 :]
            continue

        # No newline character found in the message part.
        # Try to find at least a space for a break.
        first_space = part.rfind(" ")

        if first_space != -1:
            # Space character found. 
            # Split the message by it, excluding the space itself.
            new_part = part[:first_space]
            parts.append(new_part)
            
            # Trimming msg to the length of the new part
            # and removing the space.
            msg = msg[first_space + 1 :]
            continue

        # No suitable place for a break found in the message part.
        # Add the current part and trim the message to its length.
        parts.append(part)
        msg = msg[max_msg_length:]

    return parts

