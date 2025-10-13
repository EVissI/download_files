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
    previous_player_moved = None

    for line in lines[start_idx:]:
        line = line.strip()

        # Проверяем победу
        win_match = re.match(r"Wins (\d+) points", line)
        if win_match:
            points = int(win_match.group(1))
            moves_list.append(
                {"action": "win", "player": previous_player_moved, "points": points}
            )
            continue

        # Проверяем строку с номером хода
        num_match = re.match(r"(\d+)\)\s*(.*)", line)
        if not num_match:
            continue
        turn = int(num_match.group(1))
        rest = num_match.group(2)

        # Проверяем удвоение
        double_match = re.match(r"Doubles => (\d+)\s*(Takes|Drops)", rest)
        if double_match:
            value = int(double_match.group(1))
            response = double_match.group(2).lower()
            moves_list.append(
                {"turn": turn, "player": "Red", "action": "double", "cube": value}
            )
            moves_list.append({"turn": turn, "player": "Black", "action": response})
            continue

        # --- Обработка обычных ходов ---
        dice_pattern = r"(\d)(\d):"
        dice_matches = list(re.finditer(dice_pattern, rest))
        red_part = None
        black_part = None

        if len(dice_matches) >= 1:
            red_dice_str = dice_matches[0].group(0)
            red_moves_start = dice_matches[0].end()
            if len(dice_matches) >= 2:
                red_moves_end = dice_matches[1].start()
                red_moves_str = rest[red_moves_start:red_moves_end].strip()
                black_dice_str = dice_matches[1].group(0)
                black_moves_start = dice_matches[1].end()
                black_moves_str = rest[black_moves_start:].strip()
            else:
                red_moves_str = rest[red_moves_start:].strip()
                black_dice_str = None
                black_moves_str = None

            red_part = f"{red_dice_str} {red_moves_str}".strip()
            if black_dice_str:
                black_part = f"{black_dice_str} {black_moves_str}".strip()

        def parse_part(part, player):
            if not part:
                return None
            dice_match = re.match(r"(\d)(\d):(?:\s*(.*))?", part)
            if not dice_match:
                return None

            dice = [int(dice_match.group(1)), int(dice_match.group(2))]
            moves_str = dice_match.group(3) or ""
            move_list = []

            for m in moves_str.split():
                hit = False
                if "*" in m:
                    hit = True
                    m = m.replace("*", "")
                fr_to = m.split("/")
                try:
                    fr_str = fr_to[0]
                    fr = 25 if fr_str == "Bar" else int(fr_str)
                    to = (
                        0
                        if len(fr_to) == 1
                        else (0 if fr_to[1] == "Off" else int(fr_to[1]))
                    )
                except (ValueError, IndexError):
                    continue
                move_list.append({"from": fr, "to": to, "hit": hit})

            # ✅ теперь возвращаем даже если move_list пуст
            return {"turn": turn, "player": player, "dice": dice, "moves": move_list}

        red_move = parse_part(red_part, "Red")
        if red_move:
            moves_list.append(red_move)
            previous_player_moved = "Red"

        black_move = parse_part(black_part, "Black")
        if black_move:
            moves_list.append(black_move)
            previous_player_moved = "Black"

    return moves_list


def load_game_data(file_path="output.json"):
    with open(file_path, "r") as f:
        return json.load(f)


def json_to_gnubg_commands(data):
    """
    Возвращает список токенов: {'cmd': str, 'type': 'cmd'|'hint', 'target': index_in_data_or_None}
    Это позволяет при обработке вывода однозначно привязывать результат hint к записи в augmented.
    """
    tokens = [
        {"cmd": "set player 0 name Red", "type": "cmd", "target": None},
        {"cmd": "set player 1 name Black", "type": "cmd", "target": None},
        {"cmd": "set jacoby on", "type": "cmd", "target": None},
        {"cmd": "set rng manual", "type": "cmd", "target": None},
        {"cmd": "set player 0 human", "type": "cmd", "target": None},
        {"cmd": "set player 1 human", "type": "cmd", "target": None},
        {"cmd": "new game", "type": "cmd", "target": None},
    ]

    for i, action in enumerate(data):
        player = action.get("player")
        dice = action.get("dice")
        moves = action.get("moves", [])
        act = action.get("action")

        next_act = data[i + 1].get("action") if i + 1 < len(data) else None

        if act == "double":
            tokens.append({"cmd": "double", "type": "cmd", "target": None})
        elif act == "takes":
            tokens.append({"cmd": "take", "type": "cmd", "target": None})
        elif act == "drop":
            tokens.append({"cmd": "drop", "type": "cmd", "target": None})
        elif act == "win":
            tokens.append({"cmd": "exit", "type": "cmd", "target": None})
            tokens.append({"cmd": "y", "type": "cmd", "target": None})
        elif dice:
            # Добавляем set dice как команда, а hint помечаем целевым индексом i
            tokens.append(
                {"cmd": f"set dice {dice[0]}{dice[1]}", "type": "cmd", "target": i}
            )
            tokens.append({"cmd": "hint", "type": "hint", "target": i})
            # Добавляем только если есть ходы
            if moves:
                move_cmds = [f"{m['from']}/{m['to']}" for m in moves]
                tokens.append({"cmd": " ".join(move_cmds), "type": "cmd", "target": i})
            # Добавляем roll только если следующий ход не double/takes/drop
            if next_act not in ("double", "takes", "drop"):
                tokens.append({"cmd": "roll", "type": "cmd", "target": i})

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
        result = {"type": "cube"}

        # Парсим cubeful equities
        equities = []
        for line in lines:
            if match := re.match(
                r"(\d+)\.\s+(.*?)\s+([+-]?\d+\.\d+)(?:\s+\(([+-]?\d+\.\d+)\))?$", line
            ):
                idx = int(match.group(1))
                action = match.group(2).strip()
                eq = float(match.group(3))
                equities.append({"idx": idx, "action": action, "eq": eq})

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
        r"^\s*(\d+)\.\s*(?:\([^\)]*\)\s*)?(.*?)\s+Eq\.[:]?\s*([+-]?\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    float_re = re.compile(r"[+-]?\d*\.\d+")

    while i < len(lines):
        m = entry_re.match(lines[i])
        if m:
            idx = int(m.group(1))
            move = m.group(2).strip()
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
    Extracts player nicknames from .mat file content.
    Returns tuple of (red_player, black_player)
    """
    lines = content.splitlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("Game"):
            if i + 1 < len(lines):
                players_line = lines[i + 1].strip()
                parts = players_line.split(":")
                if (
                    len(parts) >= 3
                ):  # Should have at least 3 parts: red_name : score black_name : score
                    red_player = parts[0].strip()
                    black_player = parts[2].strip()
                    logger.info(
                        f"Extracted players: Red={red_player}, Black={black_player}"
                    )
                    return red_player, black_player

    logger.warning("Could not extract player names from .mat file")
    return "Red", "Black"  # Default fallback names


def convert_moves_to_gnu(moves_list):
    """
    Converts moves to GNU backgammon format with move combining
    Returns formatted string or None if no moves
    """
    if not moves_list:
        return None

    def process_move(move):
        from_point = move["from"]
        to_point = move["to"]
        hit = "*" if move["hit"] else ""

        # Convert special points
        if from_point == 25:
            from_point = "bar"
        if to_point == 0:
            to_point = "off"

        return {"from": from_point, "to": to_point, "hit": hit}

    # Process all moves first
    processed_moves = [process_move(move) for move in moves_list]

    # Combine sequential moves
    combined_moves = []
    i = 0
    while i < len(processed_moves):
        current = processed_moves[i]
        start_point = current["from"]
        end_point = current["to"]
        hit = current["hit"]

        # Look for sequential moves
        j = i + 1
        while j < len(processed_moves):
            next_move = processed_moves[j]
            if next_move["from"] == end_point:
                # Found sequential move, update endpoint
                end_point = next_move["to"]
                hit = hit or next_move["hit"]
                j += 1
            else:
                break

        # Format the move
        from_str = str(start_point) if isinstance(start_point, int) else start_point
        to_str = "off" if end_point == 0 else str(end_point)
        move_str = f"{from_str}/{to_str}{'*' if hit else ''}"

        # Check for duplicates
        count = sum(
            1
            for k in range(i, j)
            if processed_moves[k]["from"] == processed_moves[i]["from"]
            and processed_moves[k]["to"] == processed_moves[i]["to"]
        )
        if count > 1:
            move_str = f"{move_str}({count})"

        combined_moves.append(move_str)
        i = j if j > i else i + 1

    return " ".join(combined_moves)


# Modify process_mat_file to use the extracted names
def process_mat_file(input_file, output_file):

    temp_script = random_filename()
    command_delay = 0.4
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract player names before parsing moves
        red_player, black_player = extract_player_names(content)

        parsed_moves = parse_backgammon_mat(content)

        # Add player names to the output
        for entry in parsed_moves:
            if entry.get("player") == "Red":
                entry["player_name"] = red_player
            elif entry.get("player") == "Black":
                entry["player_name"] = black_player

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(parsed_moves, f, indent=2, ensure_ascii=False)

        # генерируем токены команд
        gnubg_tokens = json_to_gnubg_commands(parsed_moves)
        logger.info([t["cmd"] for t in gnubg_tokens])

        # Инициализируем поле для подсказок в каждой записи
        for entry in parsed_moves:
            if "moves" in entry:
                entry["gnu_move"] = convert_moves_to_gnu(entry["moves"])
            entry.setdefault("hints", [])

        child = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
        time.sleep(0.5)
        try:
            try:
                start_out = child.read_nonblocking(size=4096, timeout=0.2)
                logger.debug("gnubg start output: {}", start_out)
            except Exception:
                pass

            for token in gnubg_tokens:
                line = token["cmd"]
                logger.debug("send: {}", line)
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
                    logger.debug("gnubg output after '{}':\n{}", line, out)

                if token["type"] == "hint":
                    target_idx = token.get("target")
                    hints = parse_hint_output(out)
                    if hints:
                        for h in hints:
                            parsed_moves[target_idx]["hints"].append(h)
                    else:
                        logger.debug(
                            "No hints parsed for target %s, raw output length=%d",
                            target_idx,
                            len(out),
                        )
                        parsed_moves[target_idx]["hints"].append({"raw": out})

            logger.debug("send: exit / y")
            try:
                child.sendline("exit")
                time.sleep(0.1)
                child.sendline("y")
            except Exception:
                pass

            try:
                child.expect(pexpect.EOF, timeout=10)
            except Exception:
                try:
                    child.close(force=True)
                except Exception:
                    pass

            try:
                remaining = child.read_nonblocking(size=65536, timeout=0.1)
            except Exception:
                remaining = ""
            logger.debug("gnubg final remaining: {}", remaining)

        finally:
            try:
                if child.isalive():
                    child.close(force=True)
            except Exception:
                pass

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(parsed_moves, f, indent=2, ensure_ascii=False)
            logger.info("Updated %s with hint data", output_file)
        except Exception:
            logger.exception("Failed to write augmented json with hints")
    finally:
        if os.path.exists(temp_script):
            os.remove(temp_script)
