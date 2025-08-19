import json
import re
import subprocess
import os
from loguru import logger


def parse_gnubg_output(output: str) -> dict:
    """
    Парсит вывод GNU Backgammon для извлечения никнеймов и другой информации.

    Args:
        output: Текстовый вывод GNU Backgammon.

    Returns:
        dict: Словарь с никнеймами и другой информацией.
    """
    try:
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        result = {}

        # Извлечение никнеймов рядом с доской
        board_nicknames = {}
        for line in lines:
            if line.startswith("O:"):
                board_nicknames["O"] = line.split(":")[1].strip().split("(")[0].strip()
            elif line.startswith("X:"):
                board_nicknames["X"] = line.split(":")[1].strip().split("(")[0].strip()

        # Извлечение никнеймов из строки "Player"
        player_line = next((line for line in lines if line.startswith("Player")), None)
        if player_line:
            player_nicknames = [
                nickname.strip()
                for nickname in re.split(r"\s{2,}", player_line)
                if nickname.strip()
            ]
            player_nicknames = player_nicknames[1:]  # Удаляем "Player"

        # Сравнение никнеймов
        for key, board_nickname in board_nicknames.items():
            matched_nickname = next(
                (name for name in player_nicknames if name.startswith(board_nickname)),
                board_nickname,
            )
            result[key] = matched_nickname

        return result

    except Exception as e:
        logger.error(f"Ошибка при парсинге вывода GNU Backgammon: {e}")
        raise


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

        # Используем parse_gnubg_output для извлечения никнеймов
        nicknames = parse_gnubg_output(stdout)
        logger.info(f"Извлечённые никнеймы: {nicknames}")

        # Парсинг вывода в JSON
        stats = {}
        current_section = None
        lines = [line.strip() for line in stdout.split("\n") if line.strip()]

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
                stats[current_section] = {player: {} for player in nicknames.values()}
            elif current_section and not line.startswith("|") and len(line.strip()) > 0:
                parts = [
                    p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()
                ]
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

                    if len(parts) - 1 == len(nicknames):
                        # Строки с одним значением на игрока
                        for i, player in enumerate(nicknames.values()):
                            value = parts[i + 1].strip()
                            if is_rating:
                                stats[current_section][player][key] = value
                            else:
                                main_match = re.match(r"([-\+]?[\d\.]+)", value)
                                if main_match:
                                    stats[current_section][player][key] = (
                                        main_match.group(1)
                                    )
                                bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
                                if bracket_match:
                                    stats[current_section][player][f"{key}_extra"] = (
                                        bracket_match.group(1)
                                    )
                                elif not main_match:
                                    stats[current_section][player][key] = "0"
                    elif len(parts) - 1 == 2 * len(nicknames):
                        # Строки с двумя частями на игрока (main + extra)
                        for i, player in enumerate(nicknames.values()):
                            main_part = parts[1 + 2 * i].strip()
                            extra_part = (
                                parts[2 + 2 * i].strip()
                                if 2 + 2 * i < len(parts)
                                else ""
                            )
                            value = f"{main_part} {extra_part}".strip()
                            main_match = re.match(r"([-\+]?[\d\.]+)", value)
                            if main_match:
                                stats[current_section][player][key] = main_match.group(
                                    1
                                )
                            bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
                            if bracket_match:
                                stats[current_section][player][f"{key}_extra"] = (
                                    bracket_match.group(1)
                                )
                            elif not main_match:
                                stats[current_section][player][key] = "0"
                    else:
                        logger.warning(f"Неизвестный формат строки: {line}")

        # Проверяем и исправляем значения Snowie error rate
        for player in nicknames.values():
            if (
                "overall" in stats
                and "snowie_error_rate" not in stats["overall"][player]
            ):
                stats["overall"][player]["snowie_error_rate"] = "0"

        return json.dumps(stats, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка при анализе матча: {e}")
        raise


# def analyze_mat_file_per_game(file: str, type: str = None) -> str:
#     """
#     Анализирует файл матча с помощью GNU Backgammon и возвращает статистику по каждой игре в формате JSON.

#     Args:
#         file: Путь к файлу матча или позиции.
#         type: Тип файла ('sgf', 'mat', 'sgg', 'bkg', 'gam', 'pos', 'fibs', 'tmg', 'empire', 'party'). Если None, для .gam файлов выполняется автоматическое определение.

#     Returns:
#         str: JSON-строка с результатами анализа по каждой игре.

#     Raises:
#         FileNotFoundError: Если файл или GNU Backgammon не найдены.
#         ValueError: Если указан неизвестный тип файла.
#         RuntimeError: Если произошла ошибка при выполнении GNU Backgammon.
#     """
#     try:
#         if not os.path.exists(file):
#             logger.error(f"Файл не найден: {file}")
#             raise FileNotFoundError(f"Файл не найден: {file}")

#         try:
#             subprocess.run(["gnubg", "--version"], check=True, capture_output=True)
#         except FileNotFoundError:
#             logger.error("GNU Backgammon не установлен или не найден в PATH")
#             raise FileNotFoundError("GNU Backgammon не установлен или не найден в PATH")

#         # Определение команды импорта
#         if type is None and file.endswith(".gam"):
#             # Попытка определить платформу для .gam файлов
#             with open(file, "r", encoding="utf-8", errors="ignore") as f:
#                 content = f.read().lower()
#                 if "gammonempire" in content:
#                     type = "empire"
#                 elif "partygammon" in content:
#                     type = "party"
#                 else:
#                     type = "gam"  # По умолчанию считаем Jellyfish

#         # Список команд для разных типов файлов
#         import_commands = {
#             "sgf": f"load match {file}",
#             "mat": f"import mat {file}",
#             "sgg": f"import sgg {file}",
#             "bkg": f"import bkg {file}",
#             "gam": f"import gam {file}",
#             "pos": f"import pos {file}",
#             "fibs": f"import oldmoves {file}",
#             "tmg": f"import tmg {file}",
#             "empire": f"import empire {file}",
#             "party": f"import party {file}",
#         }

#         if type not in import_commands:
#             logger.error(f"Неизвестный тип файла: {type}")
#             raise ValueError(f"Неизвестный тип файла: {type}")

#         import_command = import_commands[type]

#         # Сначала запускаем процесс для получения списка игр
#         gnubg_commands_list = [
#             import_command,
#             "analyse match",
#             "list game",
#             "exit",
#         ]

#         process_list = subprocess.Popen(
#             ["gnubg", "-t"],
#             stdin=subprocess.PIPE,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding="utf-8",
#         )
#         stdout_list, stderr_list = process_list.communicate("\n".join(gnubg_commands_list))

#         logger.debug(f"Вывод list gnubg:\n{stdout_list}")

#         # Если импорт не удался для .gam, пробуем другие команды
#         successful_type = type
#         if process_list.returncode != 0 and type in ("gam", "empire", "party"):
#             logger.warning(f"Не удалось импортировать .gam файл как {type}: {stderr_list}")
#             alternative_types = ["gam", "empire", "party"]
#             alternative_types.remove(type)
#             for alt_type in alternative_types:
#                 logger.info(f"Попытка импорта как {alt_type}")
#                 import_command_alt = import_commands[alt_type]
#                 gnubg_commands_list = [
#                     import_command_alt,
#                     "analyse match",
#                     "list game",
#                     "exit",
#                 ]
#                 process_list = subprocess.Popen(
#                     ["gnubg", "-t"],
#                     stdin=subprocess.PIPE,
#                     stdout=subprocess.PIPE,
#                     stderr=subprocess.PIPE,
#                     text=True,
#                     encoding="utf-8",
#                 )
#                 stdout_list, stderr_list = process_list.communicate("\n".join(gnubg_commands_list))
#                 if process_list.returncode == 0:
#                     logger.info(f"Успешный импорт как {alt_type}")
#                     successful_type = alt_type
#                     break
#             if process_list.returncode != 0:
#                 logger.error(f"Ошибка выполнения gnubg для всех типов .gam: {stderr_list}")
#                 raise RuntimeError(f"Ошибка выполнения gnubg: {stderr_list}")

#         if process_list.returncode != 0:
#             logger.error(f"Ошибка выполнения gnubg: {stderr_list}")
#             raise RuntimeError(f"Ошибка выполнения gnubg: {stderr_list}")

#         # Парсинг списка игр для определения количества игр
#         lines_list = [line.strip() for line in stdout_list.split("\n") if line.strip()]
#         games_lines = [line for line in lines_list if line.startswith("Game ")]
#         N = len(games_lines)
#         if N == 0:
#             logger.info("Матч не содержит игр.")
#             return json.dumps({})

#         # Теперь запускаем процесс для получения статистики по играм с успешным типом
#         import_command = import_commands[successful_type]
#         gnubg_commands_stats = [
#             import_command,
#             "analyse match",
#             "first game",
#         ]
#         for idx in range(N):
#             if idx > 0:
#                 gnubg_commands_stats.append("next game")
#             gnubg_commands_stats.append("show statistics game")
#         gnubg_commands_stats.append("exit")

#         process_stats = subprocess.Popen(
#             ["gnubg", "-t"],
#             stdin=subprocess.PIPE,
#             stdout=subprocess.PIPE,
#             stderr=subprocess.PIPE,
#             text=True,
#             encoding="utf-8",
#         )
#         stdout_stats, stderr_stats = process_stats.communicate("\n".join(gnubg_commands_stats))

#         logger.debug(f"Вывод stats gnubg:\n{stdout_stats}")

#         if process_stats.returncode != 0:
#             logger.error(f"Ошибка выполнения gnubg для статистики: {stderr_stats}")
#             raise RuntimeError(f"Ошибка выполнения gnubg для статистики: {stderr_stats}")

#         logger.info(f"Анализ матча завершён для файла: {file}. Количество игр: {N}")

#         # Парсинг вывода статистики для каждой игры
#         lines_stats = [line.strip() for line in stdout_stats.split("\n") if line.strip()]

#         stats_per_game = {}
#         player_lines_indices = [idx for idx, line in enumerate(lines_stats) if line.startswith("Player ")]
#         if len(player_lines_indices) < N:
#             logger.error("Не удалось найти статистику для всех игр.")
#             raise RuntimeError("Не удалось найти статистику для всех игр.")

#         for game_num, start_idx in enumerate(player_lines_indices[:N], start=1):
#             end_idx = player_lines_indices[game_num] if game_num < N else len(lines_stats)
#             game_lines = lines_stats[start_idx:end_idx]

#             stats = {}
#             current_section = None
#             players = []
#             for line in game_lines:
#                 if line.startswith("Player"):
#                     players = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
#                     players = players[1:]  # Удаляем "Player"
#                 elif any(header in line for header in ["Chequerplay statistics", "Luck statistics", "Cube statistics", "Overall statistics"]):
#                     current_section = line.lower().replace(" statistics", "")
#                     stats[current_section] = {player: {} for player in players}
#                 elif current_section and not line.startswith("|") and len(line.strip()) > 0:
#                     parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
#                     logger.info(parts)
#                     if len(parts) > 1:
#                         key = parts[0].lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "")
#                         if "emg" in key and not key.endswith("_points"):
#                             key = f"{key}_points"
#                         is_rating = "rating" in key
#                         if len(parts) - 1 == len(players):
#                             for j, player in enumerate(players):
#                                 value = parts[j + 1].strip()
#                                 if is_rating:
#                                     stats[current_section][player][key] = value
#                                 else:
#                                     main_match = re.match(r"([-\+]?[\d\.]+)", value)
#                                     if main_match:
#                                         stats[current_section][player][key] = main_match.group(1)
#                                     bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
#                                     if bracket_match:
#                                         stats[current_section][player][f"{key}_extra"] = bracket_match.group(1)
#                                     elif not main_match:
#                                         stats[current_section][player][key] = "0"
#                         elif len(parts) - 1 == 2 * len(players):
#                             for j, player in enumerate(players):
#                                 main_part = parts[1 + 2 * j].strip()
#                                 extra_part = parts[2 + 2 * j].strip() if 2 + 2 * j < len(parts) else ""
#                                 value = f"{main_part} {extra_part}".strip()
#                                 main_match = re.match(r"([-\+]?[\d\.]+)", value)
#                                 if main_match:
#                                     stats[current_section][player][key] = main_match.group(1)
#                                 bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
#                                 if bracket_match:
#                                     stats[current_section][player][f"{key}_extra"] = bracket_match.group(1)
#                                 elif not main_match:
#                                     stats[current_section][player][key] = "0"
#                         else:
#                             logger.warning(f"Неизвестный формат строки: {line}")

#             # Проверяем и исправляем значения Snowie error rate
#             if "overall" in stats:
#                 for player in players:
#                     if "snowie_error_rate" not in stats["overall"][player]:
#                         stats["overall"][player]["snowie_error_rate"] = "0"

#             stats_per_game[f"game_{game_num}"] = stats

#         return json.dumps(stats_per_game, ensure_ascii=False)
#     except Exception as e:
#         logger.error(f"Ошибка при анализе матча: {e}")
#         raise

# if __name__ == "__main__":
#     # Пример использования
#     try:
#         result = analyze_mat_file_per_game("test16.mat", "mat")
#         print("Результат анализа матча:", result)
#     except Exception as e:
#         print(f"Ошибка: {e}")
