import prettytable as pt
from io import BytesIO
import os
import re
from PIL import Image, ImageEnhance, ImageFilter

from loguru import logger
import pytesseract


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
            result[nick1]["quality"] = float(
                match.group(1).replace(",", ".")
            ) 
            result[nick2]["quality"] = float(
                match.group(2).replace(",", ".")
            )  
            break

    return result


def determine_rank(pr: float) -> str:
    """
    Определяет ранг пользователя на основе значения PR.
    :param pr: Performance Rating (PR)
    :return: Ранг пользователя
    """

    if pr < 2.5:
        return "World Champion"
    elif pr < 5.0:
        return "World Class"
    elif pr < 7.5:
        return "Expert"
    elif pr < 12.5:
        return "Advanced"
    elif pr < 17.5:
        return "Intermediate"
    elif pr < 22.5:
        return "Amateur"
    elif pr < 30.0:
        return "Beginner"
    else:
        return "Confused"
    
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


def get_analysis_data(analysis_data: dict, selected_player: str) -> dict:
    """Helper function to safely get analysis data with defaults"""
    chequer = analysis_data.get("chequerplay", {}).get(selected_player, {})
    luck = analysis_data.get("luck", {}).get(selected_player, {})
    cube = analysis_data.get("cube", {}).get(selected_player, {})
    overall = analysis_data.get("overall", {}).get(selected_player, {})
    luck_rate = 0
    if luck.get("luck_rate_memg_points") is not None:
        luck_rate= luck.get("luck_rate_memg_points")
    elif luck.get("luck_rate_memg_mwc_points") is not None:
        luck_rate= luck.get("luck_rate_memg_mwc_points")

    error_rate = 0
    if chequer.get("error_rate_memg_points") is not None:
        error_rate = format_value(chequer.get("error_rate_memg_points"), True)
    elif chequer.get("error_rate_memg_mwc_points") is not None:
        error_rate = format_value(chequer.get("error_rate_memg_mwc_points"), True)

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
        "cube_decision_rating": str(cube.get("cube_decision_rating", "Нет данных")),
        # Overall data
        "snowie_error_rate": float(overall.get("snowie_error_rate", 0)),
        "overall_rating": str(overall.get("overall_rating", "Нет данных")),
    }



def format_detailed_analysis(analysis_data: dict) -> str:
    """
    Форматирует результаты анализа для двух игроков в виде ASCII-таблиц для вывода в Telegram,
    с ограничением длины строк, одним числом после запятой для float, и сокращением рейтингов.
    Если ключа нет в словаре, возвращает исходное значение.
    """
    try:
        logger.info(analysis_data)
        player_names = list(analysis_data.get("chequerplay", {}).keys())
        if len(player_names) != 2:
            raise ValueError("No data found for two players")



        player1_name, player2_name = player_names
        p1 = analysis_data.get("chequerplay", {}).get(player1_name, {})
        p2 = analysis_data.get("chequerplay", {}).get(player2_name, {})
        c1 = analysis_data.get("cube", {}).get(player1_name, {})
        c2 = analysis_data.get("cube", {}).get(player2_name, {})
        l1 = analysis_data.get("luck", {}).get(player1_name, {})
        l2 = analysis_data.get("luck", {}).get(player2_name, {})
        o1 = analysis_data.get("overall", {}).get(player1_name, {})
        o2 = analysis_data.get("overall", {}).get(player2_name, {})
        max_length = 10

        # Словарь для сокращения рейтингов
        rating_shortcuts = {
            "Advanced": "Advancd",
            "Supernatural": "Supernat",
            "Expert": "Expert",
            "World class": "WorldCl",
            "None": "None",
            "Good dice, man!": "GoodDice",
            "Bad dice, man!": "BadDice",
            "Go to Las Vegas": "SuperDice",
            "Beginner": "Beginner",
            "Intermediate": "Intermed",
            "Casual player": "Casual",
            "Master": "Mastr",
            "Professional": "Pro",
            "Grandmaster": "GrandMstr",
            "No data": "N/A"
        }

        # Форматирование значений с ограничением длины и одним числом после запятой
        def format_value(val, is_float=False, max_length=max_length):
            if val is None or val == "No data":
                return "N/A".ljust(max_length)[:max_length]
            cleaned_val = re.sub(r"\s*\(.*\)", "", str(val)).strip()
            if is_float and cleaned_val:
                try:
                    num = float(cleaned_val)
                    formatted = f"{num:.1f}"
                    # Добавляем + для положительных значений
                    if num > 0:
                        formatted = f"+{formatted}"
                    return (formatted + " " * max_length)[:max_length]
                except ValueError:
                    return cleaned_val.ljust(max_length)[:max_length]
            # Применяем сокращение рейтингов, если это не float, иначе возвращаем исходное значение
            return rating_shortcuts.get(cleaned_val, cleaned_val).ljust(max_length)[:max_length]
        error_rate1 = 0
        error_rate2 = 0
        if p1.get("error_rate_memg_points") is not None:
            error_rate1 = format_value(p1.get("error_rate_memg_points"), True)
        elif p1.get("error_rate_memg_mwc_points") is not None:
            error_rate1 = format_value(p1.get("error_rate_memg_mwc_points"), True)
        if p2.get("error_rate_memg_points") is not None:
            error_rate2 = format_value(p2.get("error_rate_memg_points"), True)
        elif p2.get("error_rate_memg_mwc_points") is not None:
            error_rate2 = format_value(p2.get("error_rate_memg_mwc_points"), True)


        # Таблица для Chequerplay
        chequerplay_table = pt.PrettyTable()
        chequerplay_table.field_names = ["Param", player1_name, player2_name]
        chequerplay_table.max_width["Param"] = 15
        chequerplay_table.max_width[player1_name] = 15
        chequerplay_table.max_width[player2_name] = 15
        chequerplay_table.add_row(["Bad move", format_value(p1.get("moves_marked_bad", 0)), format_value(p2.get("moves_marked_bad", 0))])
        chequerplay_table.add_row(["Bad+ move", format_value(p1.get("moves_marked_very_bad", 0)), format_value(p2.get("moves_marked_very_bad", 0))])
        chequerplay_table.add_row(["Error rate", error_rate1, error_rate2])
        chequerplay_table.add_row(["Rating", format_value(p1.get("chequerplay_rating", "No data")), format_value(p2.get("chequerplay_rating", "No data"))])

        luck_rate1 = 0
        luck_rate2 = 0
        if l1.get("luck_rate_memg_points") is not None:
            luck_rate1= format_value(l1.get("luck_rate_memg_points"), True)
        elif l1.get("luck_rate_memg_mwc_points") is not None:
            luck_rate1= format_value(l1.get("luck_rate_memg_mwc_points"), True)
        if l2.get("luck_rate_memg_mwc_points") is not None:
            luck_rate2= format_value(l2.get("luck_rate_memg_mwc_points"), True)
        elif l2.get("luck_rate_memg_points") is not None:
            luck_rate2= format_value(l2.get("luck_rate_memg_points"), True)

        # Таблица для Luck
        luck_table = pt.PrettyTable()
        luck_table.field_names = ["Param", player1_name, player2_name]
        luck_table.max_width["Param"] = 15
        luck_table.max_width[player1_name] = 15
        luck_table.max_width[player2_name] = 15
        luck_table.add_row(["Luck+ move", format_value(l1.get("rolls_marked_very_lucky", 0)), format_value(l2.get("rolls_marked_very_lucky", 0))])
        luck_table.add_row(["Luck move", format_value(l1.get("rolls_marked_lucky", 0)), format_value(l2.get("rolls_marked_lucky", 0))])
        luck_table.add_row(["Unluck+ move", format_value(l1.get("rolls_marked_very_unlucky", 0)), format_value(l2.get("rolls_marked_very_unlucky", 0))])
        luck_table.add_row(["Unluck move", format_value(l1.get("rolls_marked_unlucky", 0)), format_value(l2.get("rolls_marked_unlucky", 0))])
        luck_table.add_row(["Luck rate", luck_rate1, luck_rate2])
        luck_table.add_row(["Rating", format_value(l1.get("luck_rating", "No data")), format_value(l2.get("luck_rating", "No data"))])

        # Таблица для Cube
        cube_table = pt.PrettyTable()
        cube_table.field_names = ["Param", player1_name, player2_name]
        cube_table.max_width["Param"] = 15
        cube_table.max_width[player1_name] = 15
        cube_table.max_width[player2_name] = 15
        cube_table.add_row(["Rating", format_value(c1.get("cube_decision_rating", "No data")), format_value(c2.get("cube_decision_rating", "No data"))])

        # Таблица для Overall
        overall_table = pt.PrettyTable()
        overall_table.field_names = ["Param", player1_name, player2_name]
        overall_table.max_width["Param"] = 15
        overall_table.max_width[player1_name] = 15
        overall_table.max_width[player2_name] = 15
        overall_table.add_row(["Error rate", format_value(o1.get("snowie_error_rate", 0), True), format_value(o2.get("snowie_error_rate", 0), True)])
        overall_table.add_row(["Rating", format_value(o1.get("overall_rating", "No data")), format_value(o2.get("overall_rating", "No data"))])

        # Формирование финального сообщения
        result = (
            f"📊 <b>Analysis results:</b>\n\n"
            f"<b>{player1_name} vs {player2_name}</b>\n\n"
            f"⚪️⚫️<b>Playing checkers:</b>\n"
            f"<pre>{chequerplay_table.get_string()}</pre>\n\n"
            f"🎯 <b>Luck:</b>\n"
            f"<pre>{luck_table.get_string()}</pre>\n\n"
            f"🎲 <b>Cube:</b>\n"
            f"<pre>{cube_table.get_string()}</pre>\n\n"
            f"📈 <b>Overall statistic:</b>\n"
            f"<pre>{overall_table.get_string()}</pre>"
        )
        return result

    except Exception as e:
        logger.error(f"Ошибка при форматировании анализа: {e}")
        return "Ошибка при форматировании результатов анализа."

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
