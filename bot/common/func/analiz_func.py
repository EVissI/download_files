import json
import re
import subprocess
import os
import tempfile
import threading
from loguru import logger

_gnubg_lock = threading.Lock()

_BEAROFF_ZERO_RE = re.compile(r"/0(\*?)(?!\d)")
_BAR_TOKEN_RE = re.compile(r"\bBar\b", re.I)
_DOUBLES_RE = re.compile(r"Doubles\s*=>\s*(\d+)", re.I)
_DROPS_RE = re.compile(r"\bDrops?\b", re.I)
_DICE_RE = re.compile(r"\d\d:")
_WINS_RE = re.compile(r"Wins\s+\d+\s+point", re.I)
_GAME_RE = re.compile(r"^Game\s+\d+", re.I)
_POINTS_MATCH_RE = re.compile(r"^\d+\s+point match", re.I)


def clean_nick(raw: str) -> str:
    """
    Убирает всё после скобок и чистит пробелы
    """
    # Отрезаем всё, что в скобках
    raw = re.sub(r"\s*\(.*?\)", "", raw)
    return raw.strip()


def convert_mat_for_gnubg(content: str) -> str:
    """
    Приводит .mat Федерации нард / похожие протоколы к Jellyfish-формату gnubg:
    комментарии ';', снятие шашек через /0, Bar/, сдача без куба.
    """
    lines_out: list[str] = []
    cube = 1
    source_lines = content.splitlines()
    for i, line in enumerate(source_lines):
        stripped = line.strip()
        if not stripped:
            lines_out.append("")
            continue
        if stripped.startswith(";"):
            continue
        if _GAME_RE.match(stripped):
            cube = 1
            lines_out.append(stripped)
            continue
        if _POINTS_MATCH_RE.match(stripped):
            lines_out.append(stripped)
            continue

        converted = _BAR_TOKEN_RE.sub("bar", line)
        converted = _BEAROFF_ZERO_RE.sub(r"/off\1", converted)

        dbl = _DOUBLES_RE.search(converted)
        if dbl:
            cube = int(dbl.group(1))
            lines_out.append(converted)
            continue

        has_drops = bool(_DROPS_RE.search(converted))
        has_dice = bool(_DICE_RE.search(converted))
        has_doubles = bool(_DOUBLES_RE.search(converted))
        if has_drops and has_dice and not has_doubles:
            converted = _DROPS_RE.sub("     ", converted)
            lines_out.append(converted)
            nxt = source_lines[i + 1].strip() if i + 1 < len(source_lines) else ""
            if not _WINS_RE.search(nxt):
                lines_out.append(f"{' ' * 37}Wins {cube} points")
            continue

        lines_out.append(converted)

    text = "\n".join(lines_out).rstrip() + "\n"
    tail = [ln for ln in text.splitlines() if ln.strip()]
    if tail and _DROPS_RE.search(tail[-1]) and not _WINS_RE.search(tail[-1]):
        text = text.rstrip() + f"\n{' ' * 37}Wins {cube} points\n"
    return text


def prepare_mat_file_for_gnubg(src: str) -> str:
    """Пишет нормализованную копию .mat во временный файл и возвращает путь."""
    with open(src, "r", encoding="utf-8", errors="ignore") as fh:
        original = fh.read()
    converted = convert_mat_for_gnubg(original)
    fd, path = tempfile.mkstemp(suffix=".mat", prefix="gnu_mat_")
    os.close(fd)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(converted)
    return path

def analyze_mat_file(file: str, type: str = None) -> tuple:
    """
    Анализирует файл матча или позиции с помощью GNU Backgammon и возвращает статистику в формате JSON,
    а также значение points match.

    Returns:
        tuple: (points_match_value, json_string)
    """
    prepared_mat = None
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
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                if "gammonempire" in content:
                    type = "empire"
                elif "partygammon" in content:
                    type = "party"
                else:
                    type = "gam"

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

        import_command = import_commands[type]
        if type == "mat":
            prepared_mat = prepare_mat_file_for_gnubg(file)
            gnu_path = prepared_mat.replace("\\", "/")
            import_command = f'import mat "{gnu_path}"'
            logger.info(f"MAT нормализован для gnubg: {prepared_mat}")
        gnubg_commands = [
            import_command,
            "analyse match",
            "show statistics match",
            "exit",
        ]

        with _gnubg_lock:
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

        stats = {}
        current_section = None
        players = []
        points_match_value = 0
        lines = [line.strip() for line in stdout.split("\n") if line.strip()]

        # Извлечение значения points match
        for line in lines:
            match = re.search(r"(\d+)\s+points match", line)
            if match:
                points_match_value = int(match.group(1))
                break

        # Извлечение строк X:, O:, и Player
        x_line = next((line for line in lines if "X:" in line), None)
        o_line = next((line for line in lines if "O:" in line), None)
        player_line = next((line for line in lines if line.strip().startswith("Player")), None)
        logger.info(f"x_line: {x_line}, o_line: {o_line}, player_line: {player_line}")
        if not x_line or not o_line or not player_line:
            logger.error("Не удалось найти строки X:, O:, или Player.")
            raise RuntimeError("Ошибка извлечения строк X:, O:, или Player.")

        x_match = re.search(r"X:\s*(.+)", x_line)
        x_nick = clean_nick(x_match.group(1)) if x_match else None

        # Ник O
        o_match = re.search(r"O:\s*(.+)", o_line)
        o_nick = clean_nick(o_match.group(1)) if o_match else None
        logger.info(f"x_nick: {x_nick}, o_nick: {o_nick}")
        # Проверим, что Player содержит оба ника
        if not (x_nick and o_nick and x_nick in player_line and o_nick in player_line):
            logger.error(f"Ошибка парсинга ников. X: {x_nick}, O: {o_nick}, Player: {player_line}")
            raise RuntimeError("Ошибка сопоставления игроков в строке Player")

        players = [o_nick, x_nick]

        if len(players) != 2 or not all(players):
            logger.error("Не удалось извлечь никнеймы игроков.")
            raise RuntimeError("Ошибка извлечения никнеймов игроков.")

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

                    if "emg" in key and not key.endswith("_points"):
                        key = f"{key}_points"

                    is_rating = "rating" in key

                    if len(parts) - 1 == len(players):
                        for i, player in enumerate(players):
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
                    elif len(parts) - 1 == 2 * len(players):
                        for i, player in enumerate(players):
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

        for player in players:
            if (
                "overall" in stats
                and "snowie_error_rate" not in stats["overall"][player]
            ):
                stats["overall"][player]["snowie_error_rate"] = "0"

        return points_match_value, json.dumps(stats, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка при анализе матча: {e}")
        raise
    finally:
        if prepared_mat:
            try:
                os.remove(prepared_mat)
            except OSError:
                pass


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
