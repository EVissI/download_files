import json
import re
import subprocess
import os
from loguru import logger


def analyze_mat_file(file: str, type: str = None) -> str:
    """
    Анализирует файл матча или позиции с помощью GNU Backgammon и возвращает статистику в формате JSON.

    Args:
        file: Путь к файлу матча или позиции.
        type: Тип файла ('sgf', 'mat', 'sgg', 'bkg', 'gam', 'pos', 'fibs', 'tmg', 'empire', 'party').
              Если None, для .gam файлов выполняется автоматическое определение.

    Returns:
        str: JSON-строка с результатами анализа.

    Raises:
        FileNotFoundError: Если файл или GNU Backgammon не найдены.
        ValueError: Если указан неизвестный тип файла.
        RuntimeError: Если произошла ошибка при выполнении GNU Backgammon.
    """
    try:
        if not os.path.exists(file):
            logger.error(f"Файл не найден: {file}")
            raise FileNotFoundError(f"Файл не найден: {file}")

        try:
            subprocess.run(["gnubg", "--version"], check=True, capture_output=True)
        except FileNotFoundError:
            logger.error("GNU Backgammon не установлен или не найден в PATH")
            raise FileNotFoundError("GNU Backgammon не установлен или не найден в PATH")

        # Определение команды импорта
        if type is None and file.endswith(".gam"):
            # Попытка определить платформу для .gam файлов
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                if "gammonempire" in content:
                    type = "empire"
                elif "partygammon" in content:
                    type = "party"
                else:
                    type = "gam"  # По умолчанию считаем Jellyfish

        # Список команд для разных типов файлов
        import_commands = {
            "sgf": f"load match {file}",
            "mat": f"import mat {file}",
            "sgg": f"import sgg {file}",
            "bkg": f"import bkg {file}",
            "gam": f"import gam {file}",
            "pos": f"import pos {file}",
            "fibs": f"import oldmoves {file}",
            "tmg": f"import tmg {file}",
            "empire": f"import empire {file}",
            "party": f"import party {file}",
        }

        if type not in import_commands:
            logger.error(f"Неизвестный тип файла: {type}")
            raise ValueError(f"Неизвестный тип файла: {type}")

        # Попытка импорта для .gam файлов с разными командами, если первая не сработала
        import_command = import_commands[type]
        gnubg_commands = [
            import_command,
            "analyse match",
            "show statistics match",
            "exit",
        ]

        process = subprocess.Popen(
            ["gnubg", "-t"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        stdout, stderr = process.communicate("\n".join(gnubg_commands))
        logger.debug(f"Вывод gnubg:\n{stdout}")

        # Если импорт не удался для .gam, пробуем другие команды
        if process.returncode != 0 and type in ("gam", "empire", "party"):
            logger.warning(f"Не удалось импортировать .gam файл как {type}: {stderr}")
            alternative_types = ["gam", "empire", "party"]
            alternative_types.remove(type)  # Удаляем уже опробованный тип

            for alt_type in alternative_types:
                logger.info(f"Попытка импорта как {alt_type}")
                gnubg_commands = [
                    import_commands[alt_type],
                    "analyse match",
                    "show statistics match",
                    "exit",
                ]
                process = subprocess.Popen(
                    ["gnubg", "-t"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                stdout, stderr = process.communicate("\n".join(gnubg_commands))
                if process.returncode == 0:
                    logger.info(f"Успешный импорт как {alt_type}")
                    break
            else:
                logger.error(f"Ошибка выполнения gnubg для всех типов .gam: {stderr}")
                raise RuntimeError(f"Ошибка выполнения gnubg: {stderr}")

        if process.returncode != 0:
            logger.error(f"Ошибка выполнения gnubg: {stderr}")
            raise RuntimeError(f"Ошибка выполнения gnubg: {stderr}")

        logger.info(f"Анализ матча завершён для файла: {file}")

        # Парсинг вывода в JSON
        stats = {}
        current_section = None
        players = []
        lines = [line.strip() for line in stdout.split("\n") if line.strip()]

        # Извлечение имен игроков
        for line in lines:
            if line.startswith("Player"):
                players = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
                players = players[1:]  # Удаляем "Player"
                break

        for line in lines:
            if any(
                header in line
                for header in [
                    "Chequerplay statistics",
                    "Luck statistics",
                    "Cube statistics",
                    "Overall statistics",
                ]
            ):
                current_section = line.lower().replace(" statistics", "")
                stats[current_section] = {player: {} for player in players}
            elif current_section and not line.startswith("|") and len(line.strip()) > 0:
                parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
                logger.info(parts)
                if len(parts) > 1:
                    key = (
                        parts[0]
                        .lower()
                        .replace(" ", "_")
                        .replace("(", "")
                        .replace(")", "")
                        .replace(".", "")
                    )

                    # Добавляем '_points' к ключам с EMG, если еще не добавлен
                    if "emg" in key and not key.endswith("_points"):
                        key = f"{key}_points"

                    is_rating = "rating" in key

                    if len(parts) - 1 == len(players):
                        # Строки с одним значением на игрока
                        for i, player in enumerate(players):
                            value = parts[i + 1].strip()
                            if is_rating:
                                stats[current_section][player][key] = value
                            else:
                                main_match = re.match(r"([-\+]?[\d\.]+)", value)
                                if main_match:
                                    stats[current_section][player][key] = main_match.group(1)
                                bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
                                if bracket_match:
                                    stats[current_section][player][f"{key}_extra"] = bracket_match.group(1)
                                elif not main_match:
                                    stats[current_section][player][key] = "0"
                    elif len(parts) - 1 == 2 * len(players):
                        # Строки с двумя частями на игрока (main + extra)
                        for i, player in enumerate(players):
                            main_part = parts[1 + 2 * i].strip()
                            extra_part = parts[2 + 2 * i].strip() if 2 + 2 * i < len(parts) else ""
                            value = f"{main_part} {extra_part}".strip()
                            main_match = re.match(r"([-\+]?[\d\.]+)", value)
                            if main_match:
                                stats[current_section][player][key] = main_match.group(1)
                            bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
                            if bracket_match:
                                stats[current_section][player][f"{key}_extra"] = bracket_match.group(1)
                            elif not main_match:
                                stats[current_section][player][key] = "0"
                    else:
                        logger.warning(f"Неизвестный формат строки: {line}")

        # Проверяем и исправляем значения Snowie error rate
        for player in players:
            if "overall" in stats and "snowie_error_rate" not in stats["overall"][player]:
                stats["overall"][player]["snowie_error_rate"] = "0"

        return json.dumps(stats, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка при анализе матча: {e}")
        raise