from collections import Counter, defaultdict
import copy
import os
from pprint import pprint
import random
import re
import json
import string
import subprocess
import sys
import time
import select
import threading
import pexpect
from loguru import logger


def check_hints_empty(data):
    """
    Проверяет, все ли hints и cube_hints пусты в файле.
    Возвращает (all_empty, empty_count, total_count)
    """
    total_count = 0
    empty_count = 0

    for entry in data:
        # Считаем только записи с dice или cube-действиями
        if entry.get("dice") or entry.get("action") in ("double", "take", "drop"):
            total_count += 1

            hints = entry.get("hints", [])
            cube_hints = entry.get("cube_hints", [])

            if not hints and not cube_hints:
                empty_count += 1

    all_empty = total_count > 0 and empty_count == total_count
    return all_empty, empty_count, total_count


def should_retry(output_file, max_retries=3):
    """
    Проверяет, нужно ли повторно запустить gnubg.

    Args:
        output_file: путь к выходному JSON файлу
        max_retries: максимальное количество повторов

    Returns:
        (should_retry: bool, retry_count: int)
    """
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        moves = data.get("moves", [])
        all_empty, empty_count, total_count = check_hints_empty(moves)

        if all_empty and total_count > 0:
            logger.warning(
                f"Обнаружены пустые hints: {empty_count}/{total_count} записей. "
                f"Требуется повтор."
            )

            # Получаем текущий счетчик повторов из metadata
            retry_count = data.get("_retry_count", 0)

            if retry_count < max_retries:
                logger.info(f"Попытка повтора #{retry_count + 1} из {max_retries}")
                return True, retry_count + 1
            else:
                logger.error(
                    f"Превышено максимальное количество повторов ({max_retries})"
                )
                return False, 0
        else:
            logger.info(
                f"Hints заполнены корректно: "
                f"{total_count - empty_count}/{total_count} записей"
            )
            return False, 0

    except Exception as e:
        logger.error(f"Ошибка при проверке hints: {e}", exc_info=True)
        return False, 0


def parse_backgammon_mat(content):
    # Убираем пустые строки, комментарии и метаданные
    lines = [
        line
        for line in content.splitlines()
        if line.strip() and not line.startswith(";") and "[" not in line
    ]

    # Находим начало ходов
    start_idx = 0
    for i, line in enumerate(lines):
        if "Game" in line:
            start_idx = i + 2  # Пропускаем строку 'Game 1' и строку счета
            break

    moves_list = []

    for line in lines[start_idx:]:
        leading_spaces = len(line) - len(line.lstrip())
        line = line.strip()
        if not line:
            continue

        # Проверяем победу (может быть с ведущими пробелами)
        # Поддерживаем форматы: "Wins 1 points", "Wins 2 point", "Wins 1 point and the match"
        win_match = re.match(r".*Wins (\d+) point(?:s)?(?:\s+and\s+the\s+match)?", line, re.I)
        if win_match:
            points = int(win_match.group(1))
            # Определяем победителя по количеству ведущих пробелов
            # Если победа на отдельной строке с большим отступом, это обычно Red
            logger.info(f"ledding space: {leading_spaces}")
            winner = "Red" if leading_spaces > 5 else "Black"
            moves_list.append({"action": "win", "player": winner, "points": points})
            continue

        # Проверяем строку с номером хода
        # Поддерживаем формат с пробелами перед номером: " 1)" или "1)"
        num_match = re.match(r"\s*(\d+)\)\s*(.*)", line)
        if not num_match:
            continue
        turn = int(num_match.group(1))
        rest = num_match.group(2)  # keep spaces

        def parse_side(side_str, player):
            if not side_str:
                return None

            # Проверяем простые действия: Takes, Drops (независимо от регистра)
            action_match = re.match(r"(Takes|Drops|Take|Drop)", side_str, re.I)
            if action_match:
                act = action_match.group(1).lower()
                if act in ["take", "takes"]:
                    act = "take"
                    gnu_move = "take"
                elif act in ["drop", "drops"]:
                    act = "drop"
                    gnu_move = "pass"
                return {
                    "turn": turn,
                    "player": player,
                    "action": act,
                    "gnu_move": gnu_move,
                }

            # Проверяем удвоение
            double_match = re.match(
                r"Doubles => (\d+)(?:\s*(Takes|Drops|Take|Drop))?", side_str, re.I
            )
            if double_match:
                value = int(double_match.group(1))
                res = {
                    "turn": turn,
                    "player": player,
                    "action": "double",
                    "cube": value,
                    "gnu_move": "Double",
                }
                response = double_match.group(2)
                if response:
                    resp_act = response.lower()
                    if resp_act in ["take", "takes"]:
                        resp_act = "take"
                        gnu_move_resp = "take"
                    elif resp_act in ["drop", "drops"]:
                        resp_act = "drop"
                        gnu_move_resp = "pass"
                    # Добавляем ответ для противоположного игрока
                    resp_player = "Black" if player == "Red" else "Red"
                    actions = resp_act.split(",")
                    moves_list.append(
                        {
                            "turn": turn,
                            "player": resp_player,
                            "action": resp_act,
                            "cube": value,
                            "gnu_move": gnu_move_resp,
                        }
                    )
                return res

            # Иначе парсим обычный ход
            # Поддерживаем формат с пробелом перед двоеточием: "43 :" или "43:"
            dice_match = re.match(r"(\d)(\d)\s*:\s*(.*)?", side_str)
            if dice_match:
                dice = [int(dice_match.group(1)), int(dice_match.group(2))]
                moves_str = dice_match.group(3) or "" if dice_match.group(3) else ""
                # Игнорируем "???" в ходах
                moves_str = moves_str.replace("???", "").strip()
                move_list = []
                for m in moves_str.split():
                    hit = False
                    if "*" in m:
                        hit = True
                        m = m.replace("*", "")
                    fr_to = m.split("/")
                    if len(fr_to) < 2:  # Требуем from/to
                        continue
                    try:
                        fr_str = fr_to[0]
                        fr = 25 if fr_str.lower() == "bar" else int(fr_str)
                        to_str = fr_to[1]
                        to = 0 if to_str.lower() == "off" else int(to_str)
                    except (ValueError, IndexError):
                        continue
                    move_list.append({"from": fr, "to": to, "hit": hit})
                return {
                    "turn": turn,
                    "player": player,
                    "dice": dice,
                    "moves": move_list,
                }

            return None

        # Check for double in the line
        double_pos = rest.find("Doubles =>")
        if double_pos != -1:
            left_part = rest[:double_pos].strip()
            right_part = rest[double_pos + len("Doubles =>") :].strip()

            right_match = re.match(r"(\d+)(?:\s*(Takes|Drops|Take|Drop))?", right_part, re.I)
            if right_match:
                value = int(right_match.group(1))
                response = (
                    right_match.group(2).lower() if right_match.group(2) else None
                )

                # Определяем, кто удваивает:
                # Если "Doubles =>" находится справа (после большого пробела), то удваивает Red
                # Если "Doubles =>" находится слева, то удваивает Black
                # Проверяем, есть ли ход слева от "Doubles =>"
                if left_part:
                    # Есть ход слева - значит "Doubles =>" справа, удваивает Red
                    double_player = "Red"
                    # Парсим ход Black (слева)
                    black_move = parse_side(left_part, "Black")
                    if black_move:
                        moves_list.append(black_move)
                else:
                    # Нет хода слева - значит "Doubles =>" слева, удваивает Black
                    double_player = "Black"

                moves_list.append(
                    {
                        "turn": turn,
                        "player": double_player,
                        "action": "double",
                        "cube": value,
                        "gnu_move": "Double",
                    }
                )

                if response:
                    if response in ["take", "takes"]:
                        response = "take"
                    elif response in ["drop", "drops"]:
                        response = "drop"
                    response_player = "Black" if double_player == "Red" else "Red"
                    gnu_move = "take" if response == "take" else "pass"
                    moves_list.append(
                        {
                            "turn": turn,
                            "player": response_player,
                            "action": response,
                            "cube": value,
                            "gnu_move": gnu_move,
                        }
                    )

            continue

        # Try split by large spaces
        parts = re.split(r"\s{10,}", rest)
        left = parts[0].strip() if len(parts) > 0 else ""
        right = parts[1].strip() if len(parts) > 1 else ""

        if len(parts) == 1:
            rest_single = rest.strip()
            # Поддерживаем формат с пробелом перед двоеточием
            dice_matches = list(re.finditer(r"(\d)(\d)\s*:", rest_single))
            if len(dice_matches) >= 2:
                red_dice_str = dice_matches[0].group(0)
                red_moves_start = dice_matches[0].end()
                red_moves_end = dice_matches[1].start()
                red_moves_str = rest_single[red_moves_start:red_moves_end].strip()
                left = f"{red_dice_str} {red_moves_str}".strip()
                black_dice_str = dice_matches[1].group(0)
                black_moves_start = dice_matches[1].end()
                black_moves_str = rest_single[black_moves_start:].strip()
                right = f"{black_dice_str} {black_moves_str}".strip()
            elif len(dice_matches) == 1:
                # Поддерживаем формат с пробелом перед двоеточием
                dice_match_original = re.search(r"(\d)(\d)\s*:", rest)
                if dice_match_original:
                    dice_pos = dice_match_original.start()
                    pre_dice = rest[:dice_pos].strip()
                    post_dice = rest[dice_pos:].strip()
                    if pre_dice and re.match(
                        r"(Takes|Drops|Take|Drop|Doubles)", pre_dice, re.I
                    ):
                        left = pre_dice
                        right = post_dice
                    else:
                        if turn == 1:
                            left = ""
                            right = post_dice
                        else:
                            left = post_dice
                            right = ""
            else:
                action_match_original = re.search(r"\S", rest)
                if action_match_original:
                    action_pos = action_match_original.start()
                    pre = rest[:action_pos].strip()
                    post = rest[action_pos:].strip()
                    if pre:
                        left = pre
                        right = post
                    else:
                        if turn == 1:
                            left = ""
                            right = post
                        else:
                            left = post
                            right = ""

        black_move = parse_side(left, "Black")
        if black_move:
            moves_list.append(black_move)
            previous_player_moved = "Black"

        red_move = parse_side(right, "Red")
        if red_move:
            moves_list.append(red_move)
            previous_player_moved = "Red"

        # Добавляем фиктивную запись для пропущенного хода (теперь слева черные, справа красные)
        if not black_move and red_move:
            skip_entry = {"turn": turn, "player": "Black", "action": "skip"}
            moves_list.insert(-1 if red_move else len(moves_list), skip_entry)
        elif black_move and not red_move:
            skip_entry = {"turn": turn, "player": "Red", "action": "skip"}
            moves_list.append(skip_entry)

    return moves_list


def load_game_data(file_path="output.json"):
    with open(file_path, "r") as f:
        return json.load(f)


def json_to_gnubg_commands(
    data,
    jacobi_rule=True,
    match_length=0,
    black_score=0,
    red_score=0,
    enable_crawford=False,
):
    """
    Возвращает список токенов: {'cmd': str, 'type': 'cmd'|'hint', 'target': index_in_data_or_None}
    Это позволяет при обработке вывода однозначно привязывать результат hint к записи в augmented.
    """
    jacoby_cmd = "set jacoby on" if jacobi_rule else "set jacoby off"
    tokens = [
        {"cmd": "set player 0 name Red", "type": "cmd", "target": None},
        {"cmd": "set player 1 name Black", "type": "cmd", "target": None},
        {"cmd": jacoby_cmd, "type": "cmd", "target": None},
        {"cmd": "set rng manual", "type": "cmd", "target": None},
        {"cmd": "set player 0 human", "type": "cmd", "target": None},
        {"cmd": "set player 1 human", "type": "cmd", "target": None},
    ]
    logger.info(f"red score:{red_score} black score {black_score}")
    if match_length > 0:
        tokens.append(
            {"cmd": f"new match {match_length}", "type": "cmd", "target": None}
        )
    else:
        tokens.append({"cmd": "new game", "type": "cmd", "target": None})

    i = 0
    skip_flag = False
    while i < len(data):
        action = data[i]
        dice = action.get("dice")
        moves = action.get("moves", [])
        act = action.get("action")

        if act == "skip":
            skip_flag = True
            i += 1
            continue
        elif act == "double":
            tokens.append({"cmd": "hint", "type": "cube_hint", "target": i})
            tokens.append({"cmd": "double", "type": "cmd", "target": None})
            i += 1
            continue
        elif act in ("take", "drop"):
            tokens.append({"cmd": "hint", "type": "cube_hint", "target": i})
            if act == "take":
                tokens.append({"cmd": "take", "type": "cmd", "target": None})
            if act == "drop":
                tokens.append({"cmd": "pass", "type": "cmd", "target": None})
            i += 1
            continue
        elif act == "win":
            tokens.append({"cmd": "exit", "type": "cmd", "target": None})
            tokens.append({"cmd": "y", "type": "cmd", "target": None})
            i += 1
            continue
        elif dice:
            tokens.append({"cmd": "roll", "type": "cmd", "target": i})
            tokens.append(
                {"cmd": f"set dice {dice[0]}{dice[1]}", "type": "cmd", "target": i}
            )
            if black_score > 0 or red_score > 0:
                if match_length > 0:
                    if enable_crawford:
                        tokens.append(
                            {"cmd": f"set crawford on", "type": "cmd", "target": None}
                        )
                tokens.append(
                    {
                        "cmd": f"set score {black_score} {red_score}",
                        "type": "cmd",
                        "target": None,
                    }
                )
                tokens.append({"cmd": f"y", "type": "cmd", "target": None})
                if skip_flag:
                    tokens.append({"cmd": "roll", "type": "cmd", "target": i})
                    tokens.append(
                        {
                            "cmd": f"set dice {dice[0]}{dice[1]}",
                            "type": "cmd",
                            "target": i,
                        }
                    )

            # Добавляем ходы, если есть
            if moves:
                tokens.append({"cmd": "hint", "type": "hint", "target": i})
                move_cmds = [
                    f"{m['from']}/{m['to']}{'*' if m['hit'] else ''}" for m in moves
                ]
                tokens.append({"cmd": " ".join(move_cmds), "type": "cmd", "target": i})
                tokens.append({"cmd": "hint", "type": "cube_hint", "target": i + 1})
            i += 1
            continue

        i += 1

    return tokens


def random_filename(ext=".gnubg", length=16):
    letters = string.ascii_letters + string.digits
    rand_str = "".join(random.choice(letters) for _ in range(length))
    return f"{rand_str}{ext}"


def read_available(proc, timeout=0.1):
    """
    Читает доступные данные из proc.stdout без блокировки (через select).
    """
    out = ""
    try:
        if proc.stdout is None:
            return out
        rlist, _, _ = select.select([proc.stdout], [], [], timeout)
        if rlist:
            out = proc.stdout.read()
    except Exception:
        try:
            # фоллбек: попытка неблокирующего чтения строк
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                out += line
        except Exception:
            pass
    return out


def read_hint_output(child, hint_type, max_wait=2.0):
    """
    Динамически читает вывод подсказки от gnubg до тех пор,
    пока не будет получен полный ответ.

    Args:
        child: pexpect процесс gnubg
        hint_type: тип подсказки ('hint' или 'cube_hint')
        max_wait: максимальное время ожидания в секундах

    Returns:
        str: полный вывод подсказки
    """
    output = ""
    start_time = time.time()
    chunk_timeout = 0.05
    last_read_time = start_time

    while time.time() - start_time < max_wait:
        try:
            # Читаем следующий chunk
            chunk = child.read_nonblocking(size=4096, timeout=chunk_timeout)
            if chunk:
                output += chunk
                last_read_time = time.time()

                if (
                    output.strip().endswith("(Red)")
                    or output.strip().endswith("(Black)")
                    or output.strip().endswith("(root)")
                    or output.strip().endswith("(gnubg)")
                ):
                    return output

                # Проверяем завершение подсказки
                if is_hint_complete(output, hint_type):
                    # Даем еще немного времени на дозавершение вывода
                    time.sleep(0.1)
                    try:
                        final_chunk = child.read_nonblocking(size=4096, timeout=0.05)
                        if final_chunk:
                            output += final_chunk
                    except:
                        pass
                    return output
            else:
                # Если долго нет новых данных, возможно подсказка завершена
                if time.time() - last_read_time > 0.5 and output.strip():
                    if output.strip().endswith("(Red)") or output.strip().endswith(
                        "(Black)"
                    ):
                        return output
                    if is_hint_complete(output, hint_type):
                        return output

        except pexpect.TIMEOUT:
            # Таймаут чтения - проверяем, не завершена ли подсказка
            if time.time() - last_read_time > 0.5 and output.strip():
                if output.strip().endswith("(Red)") or output.strip().endswith(
                    "(Black)"
                ):
                    return output
                if is_hint_complete(output, hint_type):
                    return output
            continue
        except pexpect.EOF:
            # Процесс завершился
            break
        except Exception as e:
            logger.warning(f"Error reading hint output: {e}")
            break

    logger.warning(
        f"Timeout waiting for {hint_type} completion, got partial output: {output}"
    )
    return output


def is_hint_complete(output, hint_type):
    """
    Проверяет, является ли вывод gnubg завершенной подсказкой.

    Args:
        output: накопленный вывод
        hint_type: тип подсказки ('hint' или 'cube_hint')

    Returns:
        bool: True если подсказка завершена
    """
    lines = output.strip().split("\n")
    lines = [line.strip() for line in lines if line.strip()]

    if hint_type == "cube_hint":
        # Для кубовых подсказок проверяем наличие "Proper cube action:"
        return any("Proper cube action:" in line for line in lines)

    elif hint_type == "hint":
        # Для обычных подсказок проверяем наличие завершенных ходов с equity
        # Ищем строки вида "1. Cubeful 2-ply    24/22 13/8                   Eq.: +0,008"
        hint_lines = [
            line for line in lines if re.match(r"^\d+\.\s+.*\s+Eq\.:\s*[+-]?\d+", line)
        ]
        if not hint_lines:
            return False

        # Проверяем, что после последнего хода идут вероятности (числа с плавающей точкой)
        last_hint_idx = None
        for i, line in enumerate(lines):
            if re.match(r"^\d+\.\s+.*\s+Eq\.:\s*[+-]?\d+", line):
                last_hint_idx = i

        if last_hint_idx is None:
            return False

        # После последнего хода должны быть строки с вероятностями
        remaining_lines = lines[last_hint_idx + 1 :]
        if not remaining_lines:
            return False

        # Ищем строки с числами (вероятностями)
        prob_lines = []
        for line in remaining_lines:
            # Ищем числа с плавающей точкой в строке
            floats = re.findall(r"[+-]?\d*\.\d+", line)
            if floats:
                prob_lines.append(line)

        # Должно быть хотя бы несколько строк с вероятностями
        return len(prob_lines) >= 2

    return False


def parse_hint_output(text: str):
    def clean_text(s: str) -> str:
        if not s:
            return ""
        # Удаляем backspace: симулируем эффект удаления предыдущего символа
        while "\x08" in s:
            i = s.find("\x08")
            if i <= 0:
                s = s[i + 1 :]
            else:
                s = s[: i - 1] + s[i + 1 :]
        # Нормализуем возвраты каретки и переводы строки
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        # Удаляем прочие управляющие символы
        s = re.sub(r"[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]+", "", s)
        # Разбиваем на строки и фильтруем
        lines = []
        for ln in s.splitlines():
            ln_stripped = ln.strip()
            if not ln_stripped:
                continue
            low = ln_stripped.lower()
            # Отклоняем только служебные строки
            if (
                low.startswith("hint")
                or low.startswith("considering")
                or "(black)" in low
                or "(red)" in low
            ):
                continue
            # отключаем строки из повторяющихся символов
            if re.match(r"^[\s\-=_\*\.]+$", ln_stripped):
                continue
            lines.append(ln.rstrip())
        return "\n".join(lines)

    cleaned = clean_text(text)
    if not cleaned:
        return []

    lines = [ln.rstrip() for ln in cleaned.splitlines()]

    # Проверяем наличие кубового анализа
    is_cube_analysis = any("Cube analysis" in line for line in lines)

    if is_cube_analysis:
        result = {"type": "cube_hint"}

        # Парсим cubeful equities
        equities = []
        for line in lines:
            if match := re.match(
                r"(\d+)\.\s+(.*?)\s+([+-]?\d+\.\d+)(?:\s+\(([+-]?\d+\.\d+)\))?$", line
            ):
                idx = int(match.group(1))
                action = match.group(2).strip()
                eq = float(match.group(3))
                actions = action.split(",")
                action_1 = actions[0].strip()
                action_2 = actions[1].strip() if len(actions) > 1 else None
                equities.append(
                    {"idx": idx, "action_1": action_1, "action_2": action_2, "eq": eq}
                )

        # Парсим proper cube action
        for line in lines:
            if "Proper cube action:" in line:
                result["prefer_action"] = line.split("Proper cube action:", 1)[
                    1
                ].strip()
                break

        if equities:
            result["cubeful_equities"] = equities
            return [result]

    hints = []
    i = 0
    entry_re = re.compile(
        r"^\s*(\d+)\.\s*(?:Cubeful \d+-ply\s*)?(.*?)\s+Eq\.[:]?\s*([+-]?\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    float_re = re.compile(r"[+-]?\d*\.\d+")

    while i < len(lines):
        m = entry_re.match(lines[i])
        if m:
            idx = int(m.group(1))
            move = m.group(2).strip()  # Move without "Cubeful X-ply" prefix
            try:
                eq = float(m.group(3))
            except Exception:
                eq = 0.0
            probs = []
            j = i + 1
            while j < len(lines):
                line = lines[j].strip()
                if not line:
                    break
                found = float_re.findall(line)
                if found:
                    probs.extend([float(x) for x in found])
                    j += 1
                    continue
                break
            hints.append(
                {"type": "move", "idx": idx, "move": move, "eq": eq, "probs": probs}
            )
            i = j
        else:
            i += 1
    return hints


def extract_player_names(content: str) -> tuple[str, str]:
    """
    Извлекает ники игроков из .mat файла.
    Поддерживает форматы:
    - "Peppa : 0                          Bbsm : 0" (PPNards формат)
    - "Ruslan Efimenko : 0             Anton Bulatov : 0" (Tournament формат)
    => ("Red", "Black")
    """
    lines = content.splitlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("Game"):
            if i + 1 < len(lines):
                players_line = lines[i + 1].strip()
                # Находим все пары вида "Имя : число"
                # Используем более гибкий паттерн для поддержки имен с пробелами
                matches = re.findall(r"([^:]+?)\s*:\s*(\d+)", players_line)
                if len(matches) >= 2:
                    black_player = matches[0][0].strip()
                    red_player = matches[1][0].strip()
                    logger.info(
                        f"Extracted players: Red={red_player}, Black={black_player}"
                    )
                    return red_player, black_player

    logger.warning("Could not extract player names from .mat file")
    return "Black", "Red"


def extract_match_length(content: str) -> int:
    """
    Извлекает длину матча из .mat файла.
    Пример: "15 point match"
    => 15
    """
    lines = content.splitlines()

    for line in lines:
        match = re.match(r"(\d+)\s+point match", line.strip())
        if match:
            return int(match.group(1))

    logger.warning("Could not extract match length from .mat file")
    return 0


def extract_jacobi_rule(content: str) -> bool:
    """
    Извлекает правило Якоби из .mat файла.
    Поддерживает форматы:
    - ";Jacobi rule: True" (PPNards формат)
    - "; [Jacobi "True"]" (Tournament формат)
    По умолчанию True, если не найдено.
    """
    lines = content.splitlines()

    for line in lines:
        # Формат PPNards: ";Jacobi rule: True"
        match = re.match(r";Jacobi rule:\s*(True|False)", line.strip(), re.I)
        if match:
            return match.group(1).lower() == "true"
        
        # Формат Tournament: "; [Jacobi "True"]"
        match = re.search(r'\[Jacobi\s+"(True|False)"\]', line, re.I)
        if match:
            return match.group(1).lower() == "true"

    logger.warning("Could not extract Jacobi rule from .mat file, defaulting to True")
    return True


def normalize_move(move_str: str) -> str:
    """
    Нормализует строку хода: убирает пробелы, сортирует части для независимости от порядка,
    канонизирует позицию хита для эквивалентных ходов (e.g., "8/7* 13/7" == "13/7* 8/7").
    """
    moves = parse_gnu_move(move_str)
    if not moves:
        return ""

    # Convert to tuples (from, to, hit)
    move_tuples = [(m["from"], m["to"], m["hit"]) for m in moves]

    # Sort by from desc, to desc, hit True first
    move_tuples.sort(key=lambda x: (-x[0], -x[1], -int(x[2])))

    # Merge chains skipping intermediate points without hits
    merged_tuples = []
    i = 0
    while i < len(move_tuples):
        fr, to, hit = move_tuples[i]
        j = i + 1
        while j < len(move_tuples) and move_tuples[j][0] == to and not hit:
            to = move_tuples[j][1]
            hit = move_tuples[j][2]
            j += 1
        merged_tuples.append((fr, to, hit))
        i = j

    # Canonicalize hits: collect per to
    hit_to = defaultdict(bool)
    for fr, to, hit in merged_tuples:
        hit_to[to] |= hit

    # Assign hit to first move per to
    need_hit = set(to for to in hit_to if hit_to[to])
    new_tuples = []
    for fr, to, _ in merged_tuples:
        hit = False
        if to in need_hit:
            hit = True
            need_hit.discard(to)
        new_tuples.append((fr, to, hit))

    # Rebuild moves list
    new_moves = [{"from": fr, "to": to, "hit": hit} for fr, to, hit in new_tuples]

    # Combine and return
    return convert_moves_to_gnu(new_moves) or ""


def parse_gnu_move(move_str: str):
    if not move_str:
        return []

    parts = move_str.split()
    moves = []
    for part in parts:
        hit = part.endswith("*")
        if hit:
            part = part[:-1]

        count = 1
        base = part
        if "(" in part and part.endswith(")"):
            base, count_str = part.rsplit("(", 1)
            count = int(count_str[:-1])

        segments = [s.lower() for s in base.split("/") if s]
        if not segments:
            continue

        fr_str = segments[0]
        hit_fr = fr_str.endswith("*")
        if hit_fr:
            fr_str = fr_str[:-1]
        fr = (
            25
            if fr_str == "bar"
            else int(fr_str) if fr_str.isdigit() else 0 if fr_str == "off" else None
        )
        if fr is None:
            continue

        for _ in range(count):
            prev = fr
            for seg in segments[1:]:
                hit_seg = seg.endswith("*")
                if hit_seg:
                    seg = seg[:-1]
                to = (
                    25
                    if seg == "bar"
                    else 0 if seg == "off" else int(seg) if seg.isdigit() else None
                )
                if to is None:
                    break
                moves.append({"from": prev, "to": to, "hit": hit_seg})
                prev = to

        if hit_fr and moves:
            moves[0]["hit"] = True

        if hit:
            if moves:
                moves[-1]["hit"] = True

    return moves


def convert_moves_to_gnu(moves_list):
    if not moves_list:
        return None

    def fmt(pos):
        if pos == 25:
            return "bar"
        if pos == 0:
            return "off"
        return str(pos)

    # Count parallel edges and record if any hit exists on that edge
    edges = defaultdict(int)  # (fr,to) -> count
    edge_hit = defaultdict(bool)  # (fr,to) -> True if any hit on that edge

    for m in moves_list:
        fr = m["from"]
        to = m["to"]
        edges[(fr, to)] += 1
        if m.get("hit"):
            edge_hit[(fr, to)] = True

    def build_degree_maps():
        out = defaultdict(int)
        inn = defaultdict(int)
        for (a, b), cnt in edges.items():
            if cnt > 0:
                out[a] += cnt
                inn[b] += cnt
        return out, inn

    result_parts = []

    while True:
        remaining = [(e, c) for e, c in edges.items() if c > 0]
        if not remaining:
            break

        out_map, in_map = build_degree_maps()

        # Prefer start nodes that are not destinations (sources)
        candidate_starts = [
            a for (a, b), c in edges.items() if c > 0 and in_map.get(a, 0) == 0
        ]
        if not candidate_starts:
            # fallback: choose node with largest out-degree (tie: largest node)
            cand = {}
            for (fr, to), cnt in edges.items():
                if cnt > 0:
                    cand.setdefault(fr, 0)
                    cand[fr] += cnt
            if cand:
                max_out = max(cand.values())
                candidate_starts = [n for n, v in cand.items() if v == max_out]
            else:
                candidate_starts = [e[0][0] for e in remaining]

        # deterministic pick: prefer higher position (so bar=25 goes first)
        start = max(candidate_starts)

        # build path greedily: pick outgoing edge with largest remaining count; tie-breaker: largest 'to'
        path = []
        cur = start
        while True:
            next_edges = [
                (to, edges[(cur, to)])
                for (fr, to) in edges.keys()
                if fr == cur and edges[(fr, to)] > 0
            ]
            if not next_edges:
                break
            next_edges.sort(key=lambda x: (x[1], x[0]), reverse=True)
            nxt = next_edges[0][0]
            path.append((cur, nxt))
            cur = nxt

        if not path:
            # consume any single outgoing edge or any remaining edge
            single = None
            for (fr, to), cnt in edges.items():
                if cnt > 0 and fr == start:
                    single = (fr, to)
                    break
            if single is None:
                single = remaining[0][0]
            path = [single]

        # multiplicity k = min count along path
        counts = [edges[e] for e in path]
        k = min(counts)

        # determine if any hits on edges, and whether any middle-edge hits exist
        hits_per_edge = [edge_hit[e] for e in path]
        any_hit = any(hits_per_edge)
        middle_hits = any(hits_per_edge[:-1]) if len(hits_per_edge) > 1 else False
        last_edge_hit = hits_per_edge[-1]

        # Build output depending on hits
        if len(path) == 1:
            # single edge: straightforward
            fr, to = path[0]
            move_str = f"{fmt(fr)}/{fmt(to)}"
            if last_edge_hit:
                move_str += "*"
            if k > 1:
                move_str += f"({k})"
        else:
            if middle_hits:
                # expand full chain and mark each landing that had hit
                parts = [fmt(path[0][0])]
                for (fr, to), hit in zip(path, hits_per_edge):
                    landing = fmt(to)
                    if hit:
                        landing += "*"
                    parts.append(landing)
                move_str = "/".join(parts)
                if k > 1:
                    # append multiplicity to final landing
                    move_str += f"({k})"
            else:
                # no middle hits: compress to start/.../final and add * only if last edge was hit
                move_str = f"{fmt(path[0][0])}/{fmt(path[-1][1])}"
                if last_edge_hit:
                    move_str += "*"
                if k > 1:
                    move_str += f"({k})"

        result_parts.append(move_str)

        # decrement counts along path by k
        for e in path:
            edges[e] -= k
            if edges[e] <= 0:
                edges[e] = 0
                edge_hit[e] = False

    final = " ".join(result_parts)
    # logger.debug(f"Converted to GNU: {final}")
    return final or None


class BackgammonPositionTracker:
    def __init__(self, invert_colors=False):
        self.invert_colors = invert_colors
        # Always use standard positions as base
        self.start_positions = {
            "red": {"bar": 0, "off": 0, 6: 5, 8: 3, 13: 5, 24: 2},
            "black": {"bar": 0, "off": 0, 1: 2, 12: 5, 17: 3, 19: 5},
        }
        self.reset()

    def reset(self):
        self.positions = copy.deepcopy(self.start_positions)
        self.current_player = (
            "red" if not self.invert_colors else "black"
        )  # красные начинают, если не инвертировано

    @staticmethod
    def invert_point(point: int) -> int:
        if point in (0, 25):
            return point
        return 25 - point

    def _key(self, n):
        if n == 0:
            return "off"
        if n == 25:
            return "bar"
        return n

    def _dec(self, side, k):
        cur = self.positions[side].get(k, 0)
        if cur > 1:
            self.positions[side][k] = cur - 1
        elif cur == 1:
            if k in ("bar", "off"):
                self.positions[side][k] = 0
            else:
                self.positions[side].pop(k)
        else:
            pass
            # logger.debug("warning: removing empty point %s %s", side, k)

    def _inc(self, side, k):
        self.positions[side][k] = self.positions[side].get(k, 0) + 1

    def apply_move(self, player, move):
        fr, to, hit = move.get("from"), move.get("to"), move.get("hit", False)
        if self.invert_colors:
            if player == "red":
                fr = self.invert_point(fr)
                to = self.invert_point(to)
        else:
            if player == "black":
                fr = self.invert_point(fr)
                to = self.invert_point(to)

        key_fr, key_to = self._key(fr), self._key(to)
        opp = "red" if player == "black" else "black"

        self._dec(player, key_fr)

        if hit and key_to != "off":
            if self.positions[opp].get(key_to, 0) > 0:
                self._dec(opp, key_to)
                self._inc(opp, "bar")

        self._inc(player, key_to)

    def process_game(self, data: list):
        self.reset()
        result = []

        for entry in data:
            e = copy.deepcopy(entry)
            action = e.get("action")
            player = e.get("player", self.current_player).lower()

            # обработка удвоений и ответов
            if action:
                act = action.lower()
                if act == "skip":
                    # skip не меняет позиции и очередь
                    e["positions"] = copy.deepcopy(self.positions)
                    inverted_positions = self._invert_positions(self.positions)
                    e["inverted_positions"] = inverted_positions
                    result.append(e)
                    continue
                elif act == "double":
                    # право хода не меняется
                    pass
                elif act in ("take", "drop"):
                    # право хода переходит к другому
                    self.current_player = (
                        "black" if self.current_player == "red" else "red"
                    )
                e["positions"] = copy.deepcopy(self.positions)
                # Create inverted positions
                inverted_positions = self._invert_positions(self.positions)
                e["inverted_positions"] = inverted_positions
                result.append(e)
                continue

            # обработка обычных ходов
            moves = e.get("moves")
            if moves:
                for m in moves:
                    self.apply_move(player, m)

            # после обычного хода — передаём очередь
            self.current_player = "black" if player == "red" else "red"
            e["positions"] = copy.deepcopy(self.positions)
            # Create inverted positions
            inverted_positions = self._invert_positions(self.positions)
            e["inverted_positions"] = inverted_positions
            result.append(e)

        return result

    def _invert_positions(self, positions):
        """Invert the positions for the board"""
        inverted = {"red": {}, "black": {}}
        for color in ["red", "black"]:
            for key, value in positions[color].items():
                if key == "bar" or key == "off":
                    inverted[color][key] = value
                else:
                    inverted_point = 25 - int(key)
                    inverted[color][str(inverted_point)] = value
        return inverted


def parse_mat_games(content):
    """
    Разбирает .mat файл на отдельные игры.
    Возвращает список словарей с ключами: 'game_number', 'red_player', 'black_player', 'content'
    """
    games = []
    lines = content.splitlines()
    current_game = None
    game_content = []

    for line in lines:
        if line.strip().startswith("Game"):
            # Сохраняем предыдущую игру, если она есть
            if current_game is not None:
                games.append(
                    {
                        "game_number": current_game,
                        "red_player": red_player,
                        "black_player": black_player,
                        "red_score": red_score,
                        "black_score": black_score,
                        "content": "\n".join(game_content),
                    }
                )

            # Начинаем новую игру
            match = re.match(r"Game (\d+)", line.strip())
            if match:
                current_game = int(match.group(1))
                game_content = [line]  # Начинаем с заголовка игры
                red_player = None
                black_player = None
                red_score = None
                black_score = None
        elif current_game is not None:
            game_content.append(line)
            # Ищем строку с именами игроков и счетами
            # Используем более гибкий паттерн для поддержки имен с пробелами
            if ":" in line and not red_player:
                matches = re.findall(r"([^:]+?)\s*:\s*(\d+)", line)
                if len(matches) >= 2:
                    black_player = matches[0][0].strip()
                    black_score = int(matches[0][1])
                    red_player = matches[1][0].strip()
                    red_score = int(matches[1][1])

    # Сохраняем последнюю игру
    if current_game is not None:
        games.append(
            {
                "game_number": current_game,
                "red_player": red_player,
                "black_player": black_player,
                "red_score": red_score,
                "black_score": black_score,
                "content": "\n".join(game_content),
            }
        )

    return games


def process_single_game(game_data, output_dir, game_number):
    """
    Обрабатывает одну игру и сохраняет результат в отдельный файл.
    Возвращает путь к файлу с результатом.
    """
    game_content = game_data["content"]
    red_player = game_data["red_player"]
    black_player = game_data["black_player"]

    # Парсим ходы игры
    parsed_moves = parse_backgammon_mat(game_content)
    tracker = BackgammonPositionTracker()
    aug = tracker.process_game(parsed_moves)

    # Добавляем имена игроков
    for entry in aug:
        if entry.get("player") == "Red":
            entry["player_name"] = red_player
        elif entry.get("player") == "Black":
            entry["player_name"] = black_player

    # Конвертируем ходы в GNU формат
    for entry in aug:
        if "moves" in entry:
            entry["gnu_move"] = convert_moves_to_gnu(entry["moves"])
            entry["gnu_move"] = normalize_move(entry["gnu_move"]) or entry["gnu_move"]

    # Генерируем токены команд для gnubg
    gnubg_tokens = json_to_gnubg_commands(
        aug,
        game_data["jacobi_rule"],
        game_data["match_length"],
        game_data["black_score"],
        game_data["red_score"],
        game_data["enable_crawford"],
    )
    logger.info(f"Game {game_number} tokens: {[t['cmd'] for t in gnubg_tokens]}")

    # Инициализируем поле для подсказок
    for entry in aug:
        entry.setdefault("hints", [])
        entry.setdefault("cube_hints", [])

    retry_count = 0
    max_retries = 3
    temp_file = os.path.join(output_dir, f"temp_{game_number}.json")

    while retry_count <= max_retries:
        # Запускаем gnubg для этой игры
        child = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
        command_delay = 0
        try:
            time.sleep(0.2)
            try:
                start_out = child.read_nonblocking(size=4096, timeout=0.2)
                # logger.debug(f"Game {game_number} gnubg start output: {start_out}")
            except Exception:
                pass

            for token in gnubg_tokens:
                line = token["cmd"]
                # logger.debug(f"Game {game_number} send: {line}")
                child.sendline(line)
                time.sleep(command_delay)

                out = ""
                while True:
                    try:
                        chunk = child.read_nonblocking(size=4096, timeout=0.05)
                        if not chunk:
                            break
                        out += chunk
                    except pexpect.TIMEOUT:
                        break
                    except pexpect.EOF:
                        break
                    except Exception:
                        break

                if out:
                    pass
                    # logger.debug(f"Game {game_number} gnubg output after '{line}':\n{out}")

                if token["type"] in ("hint", "cube_hint"):
                    target_idx = token.get("target")

                    # Динамическое чтение вывода подсказки
                    hint_output = read_hint_output(child, token["type"])
                    out += hint_output

                    hints = parse_hint_output(out)
                    if hints:
                        for h in hints:
                            match token["type"]:
                                case "cube_hint":
                                    aug[target_idx]["cube_hints"].append(h)
                                case "hint":
                                    aug[target_idx]["hints"].append(h)
                    else:
                        pass
                        # logger.debug(
                        #     f"Game {game_number} no hints parsed for target {target_idx}, raw output length={len(out)}"
                        # )

            # Проверяем необходимость повтора
            temp_data = {"moves": aug, "_retry_count": retry_count}
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(temp_data, f, ensure_ascii=False)

            should_retry_flag, new_retry_count = should_retry(temp_file, max_retries)
            if not should_retry_flag:
                break
            retry_count = new_retry_count
            # Очищаем hints для повтора
            for entry in aug:
                entry["hints"] = []
                entry["cube_hints"] = []
            logger.info(f"Повтор игры {game_number}, попытка {retry_count}")

            # logger.debug(f"Game {game_number} send: exit / y")
            try:
                child.sendline("exit")
                time.sleep(0.1)
                child.sendline("y")
                time.sleep(0.5)
            except Exception:
                pass

            try:
                child.expect(pexpect.EOF, timeout=10)
            except Exception:
                try:
                    child.close(force=True)
                except Exception:
                    pass

        finally:
            try:
                if child.isalive():
                    child.close(force=True)
            except Exception:
                pass

    # Удаляем временный файл
    try:
        os.remove(temp_file)
    except Exception:
        pass

    # Сравниваем ходы с подсказками
    for idx, entry in enumerate(aug):
        if entry.get("gnu_move"):
            if (
                "gnu_move" in entry
                and entry.get("hints")
                and entry.get("gnu_move").lower() not in ("double", "take", "pass")
            ):
                first_hint = next(
                    (
                        hint
                        for hint in entry["hints"]
                        if hint.get("idx") == 1 and hint.get("type") == "move"
                    ),
                    None,
                )
                if first_hint and "move" in first_hint:
                    normalized_gnu = normalize_move(entry["gnu_move"])
                    normalized_hint = normalize_move(first_hint["move"])
                    entry["is_best_move"] = normalized_gnu == normalized_hint

                    if not entry["is_best_move"]:
                        pass
                        # logger.debug(
                        #     f"Game {game_number} move mismatch: gnu_move='{entry['gnu_move']}' (normalized: '{normalized_gnu}') vs hint='{first_hint['move']}' (normalized: '{normalized_hint}')"
                        # )
                else:
                    entry["is_best_move"] = False
                    logger.warning(
                        f"Game {game_number} no valid first hint for entry: {entry}"
                    )
            elif entry.get("cube_hints") and entry.get("gnu_move") == "Double":
                logger.info(
                    f"Game {game_number} evaluating double move for entry idx {idx}"
                )

                # Сразу ставим False, чтобы ключ гарантированно существовал
                entry["is_best_move"] = False

                try:
                    # 1. Безопасно получаем эквити текущей позиции
                    cubeful_equities = (entry.get("cube_hints") or [{}])[0].get(
                        "cubeful_equities", []
                    )
                    no_double_record = next(
                        (
                            item
                            for item in cubeful_equities
                            if str(item.get("action_1") or "").lower() == "no double"
                        ),
                        None,
                    )

                    # Если нет данных по эквити, мы не можем оценить ход
                    if not no_double_record:
                        logger.warning(
                            f"Game {game_number}: No 'no double' equity data for Double evaluation"
                        )
                        continue

                    next_action = "unknown"
                    if idx + 1 < len(aug):
                        next_move_raw = aug[idx + 1].get("gnu_move")
                        if next_move_raw:
                            next_action = next_move_raw.lower()

                    # 3. Выбираем с чем сравнивать
                    compare_record = None

                    if next_action == "take":
                        compare_record = next(
                            (
                                item
                                for item in cubeful_equities
                                if str(item.get("action_2") or "").lower() == "take"
                            ),
                            None,
                        )
                    elif next_action == "pass":
                        compare_record = next(
                            (
                                item
                                for item in cubeful_equities
                                if str(item.get("action_2") or "").lower() == "pass"
                            ),
                            None,
                        )
                    else:
                        logger.warning(
                            f"Game {game_number}: Next move '{next_action}' not recognized or missing. Using 'take' equity for comparison."
                        )
                        compare_record = next(
                            (
                                item
                                for item in cubeful_equities
                                if str(item.get("action_2") or "").lower() == "take"
                            ),
                            None,
                        )

                    # 4. Финальное сравнение
                    if (
                        compare_record
                        and compare_record.get("eq") is not None
                        and no_double_record.get("eq") is not None
                    ):
                        if compare_record["eq"] > no_double_record["eq"]:
                            entry["is_best_move"] = True
                        else:
                            entry["is_best_move"] = False

                        logger.info(
                            f"Result: {entry['is_best_move']} (Double Eq: {compare_record['eq']} vs NoDouble Eq: {no_double_record['eq']})"
                        )
                    else:
                        logger.warning(
                            f"Game {game_number}: Could not find equity records to compare"
                        )

                except Exception as e:
                    logger.warning(
                        f"Game {game_number} error evaluating double: {e}",
                        exc_info=True,
                    )
            elif entry.get("cube_hints") and entry.get("gnu_move").lower() == "take":
                cubeful_equities = (entry.get("cube_hints") or [{}])[0].get(
                    "cubeful_equities"
                )
                if cubeful_equities:
                    take_record = next(
                        (
                            item
                            for item in cubeful_equities
                            if str(item.get("action_2") or "").lower() == "take"
                        ),
                        None,
                    )
                    pass_record = next(
                        (
                            item
                            for item in cubeful_equities
                            if str(item.get("action_2") or "").lower() == "pass"
                        ),
                        None,
                    )
                    if (
                        take_record
                        and pass_record
                        and take_record.get("eq") is not None
                        and pass_record.get("eq") is not None
                    ):
                        entry["is_best_move"] = take_record.get("eq") > pass_record.get(
                            "eq"
                        )
                    else:
                        entry["is_best_move"] = False
                else:
                    entry["is_best_move"] = False
            else:
                entry["is_best_move"] = False
        else:
            entry["is_best_move"] = False

    # Сохраняем результат в отдельный файл
    game_output_file = os.path.join(output_dir, f"game_{game_number}.json")
    game_data_json = {
        "game_info": {
            "game_number": game_number,
            "red_player": red_player,
            "black_player": black_player,
            "scores": {
                "Red": game_data["red_score"],
                "Black": game_data["black_score"],
            },
            "match_length": game_data["match_length"],
            "jacobi_rule": game_data["jacobi_rule"],
        },
        "moves": aug,
    }
    with open(game_output_file, "w", encoding="utf-8") as f:
        json.dump(game_data_json, f, indent=2, ensure_ascii=False)
    logger.info(f"Game {game_number} processed and saved to {game_output_file}")

    return game_output_file


def estimate_processing_time(mat_file_path):
    """
    Оценивает время выполнения обработки .mat файла на основе его содержимого.
    Возвращает примерное время в секундах (максимальное из игр).
    """
    try:
        with open(mat_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        games = parse_mat_games(content)
        if not games:
            return 0

        match_length = extract_match_length(content)
        jacobi_rule = extract_jacobi_rule(content)

        max_estimated_time = 0
        for game_data in games:
            game_data["match_length"] = match_length
            game_data["jacobi_rule"] = jacobi_rule

            # Парсим ходы игры
            parsed_moves = parse_backgammon_mat(game_data["content"])
            tracker = BackgammonPositionTracker()
            aug = tracker.process_game(parsed_moves)

            # Добавляем имена игроков
            for entry in aug:
                if entry.get("player") == "Red":
                    entry["player_name"] = game_data["red_player"]
                elif entry.get("player") == "Black":
                    entry["player_name"] = game_data["black_player"]

            # Конвертируем ходы в GNU формат
            for entry in aug:
                if "moves" in entry:
                    entry["gnu_move"] = convert_moves_to_gnu(entry["moves"])

            # Генерируем токены команд для gnubg
            gnubg_tokens = json_to_gnubg_commands(
                aug,
                game_data["jacobi_rule"],
                game_data["match_length"],
                game_data["black_score"],
                game_data["red_score"],
            )

            # Считаем количество hint команд
            hint_count = sum(
                1 for token in gnubg_tokens if token["type"] in ("hint", "cube_hint")
            )

            # Оцениваем время: каждый hint ~2 секунды, плюс overhead ~10 секунд на игру
            estimated_time = hint_count * 2 + 10
            if estimated_time > max_estimated_time:
                max_estimated_time = estimated_time

        return max_estimated_time

    except Exception as e:
        logger.error(f"Error estimating processing time for {mat_file_path}: {e}")
        return 0


def process_mat_file(input_file, output_file, chat_id):
    """
    Основная функция обработки .mat файла.
    Поддерживает как одиночные игры, так и множественные игры.
    """
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Разбираем файл на игры
        games = parse_mat_games(content)

        if not games:
            raise ValueError("No games found in .mat file")

        # Определяем глобальную информацию об игроках
        first_game = games[0]
        red_player = first_game["red_player"]
        black_player = first_game["black_player"]
        red_score = first_game["red_score"]
        black_score = first_game["black_score"]
        match_length = extract_match_length(content)
        jacobi_rule = extract_jacobi_rule(content)

        # Находим первую игру, где счет достигает match_length - 1
        crawford_game = None
        for game in games:
            if (
                game["black_score"] == match_length - 1
                or game["red_score"] == match_length - 1
            ):
                crawford_game = game["game_number"]
                break

        # Создаем директорию для результатов
        output_dir = output_file.rsplit(".", 1)[0] + "_games"
        os.makedirs(output_dir, exist_ok=True)

        # Обрабатываем игры параллельно
        import concurrent.futures

        game_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for game_data in games:
                game_data["match_length"] = match_length
                game_data["jacobi_rule"] = jacobi_rule
                game_data["enable_crawford"] = game_data["game_number"] == crawford_game
                if game_data["enable_crawford"]:
                    enable_crawford_game_number = game_data["game_number"]
                future = executor.submit(
                    process_single_game, game_data, output_dir, game_data["game_number"]
                )
                futures.append((game_data["game_number"], future))

            for game_number, future in futures:
                try:
                    result_file = future.result()
                    game_results.append(
                        {"game_number": game_number, "result_file": result_file}
                    )
                    logger.info(f"Game {game_number} processing completed")
                except Exception as e:
                    logger.error(f"Failed to process game {game_number}: {e}")

        # Создаем общий результат
        game_info = {
            "red_player": red_player,
            "black_player": black_player,
            "scores": {"Red": red_score, "Black": black_score},
            "match_length": match_length,
            "enable_crawford_game": (
                enable_crawford_game_number if crawford_game else None
            ),
            "jacobi_rule": jacobi_rule,
            "chat_id": str(chat_id),
            "total_games": len(games),
            "processed_games": len(game_results),
        }

        output_data = {"game_info": game_info, "games": game_results}

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(
            f"Processed {len(game_results)} games from {input_file}, saved to {output_file}"
        )

    except Exception as e:
        logger.exception(f"Failed to process mat file {input_file}: {e}")
        raise
