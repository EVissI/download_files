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


class BackgammonBoard:
    def __init__(self):
        self.board = [0] * 26
        # Red positions (positive)
        self.board[24] = 2
        self.board[13] = 5
        self.board[8] = 3
        self.board[6] = 5
        # Black positions (negative)
        self.board[1] = -2
        self.board[12] = -5
        self.board[17] = -3
        self.board[19] = -5
        self.off_red = 0
        self.off_black = 0

    def _get_fixed_point(self, p, player):
        if player == "Red":
            if p == 25:
                return 0  # Red bar
            elif p == 0:
                return None  # bear off
            else:
                return p
        else:  # Black
            if p == 25:
                return 25  # Black bar
            elif p == 0:
                return None  # bear off
            else:
                return 25 - p

    def apply_move(self, player, fr, to, hit):
        f_fixed = self._get_fixed_point(fr, player)
        t_fixed = self._get_fixed_point(to, player)

        if f_fixed is None:
            raise ValueError("Cannot move from bear off")

        # Determine signs and bars
        if player == "Red":
            sign = 1
            bar_own = 0
            bar_opp = 25
        else:
            sign = -1
            bar_own = 25
            bar_opp = 0

        # Remove from from
        if f_fixed == bar_own:
            self.board[bar_own] -= 1
        else:
            self.board[f_fixed] -= sign

        # Add to to
        if t_fixed is None:
            # Bear off
            if player == "Red":
                self.off_red += 1
            else:
                self.off_black += 1
        else:
            # Check for hit
            if self.board[t_fixed] == -sign:  # single opponent
                self.board[t_fixed] = 0
                self.board[bar_opp] += 1  # opponent to bar
            self.board[t_fixed] += sign

    def get_positions(self):
        red_pos = {"bar": self.board[0], "off": self.off_red}
        black_pos = {"bar": self.board[25], "off": self.off_black}
        for i in range(1, 25):
            if self.board[i] > 0:
                red_pos[i] = self.board[i]
            elif self.board[i] < 0:
                black_pos[i] = -self.board[i]
        return {"red": red_pos, "black": black_pos}


def load_game_data(file_path="output.json"):
    with open(file_path, "r") as f:
        return json.load(f)


def process_game(game_data):
    board = BackgammonBoard()
    augmented = []
    for entry in game_data:
        augmented_entry = copy.deepcopy(entry)
        if "moves" in entry:
            for move in entry["moves"]:
                board.apply_move(entry["player"], move["from"], move["to"], move["hit"])
        if (
            "positions" not in augmented_entry
        ):  # For non-move entries like double, takes, win
            augmented_entry["positions"] = board.get_positions()
        else:
            augmented_entry["positions"] = board.get_positions()
        augmented.append(augmented_entry)
    return augmented


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
    """
    Парсит блоки подсказок из вывода gnubg после команды "hint".
    Возвращает список словарей: {"idx": int, "move": str, "eq": float, "probs": [float,...]}
    Работает достаточно гибко: ищет строки вида:
      1. (...) Cubeful 0-ply    6/off 5/off                 Eq.: +1.619
        0.962 0.647 0.061 -0.038 0.000 0.000
    и аналогичные варианты.
    """
    hints = []
    lines = [ln.rstrip() for ln in text.splitlines()]
    i = 0
    entry_re = re.compile(
        r"^\s*(\d+)\.\s*(?:\([^\)]*\)\s*)?(.*?)\s+Eq\.\s*[:]?\s*([+-]?\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    float_re = re.compile(r"[+-]?\d+\.\d+")
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
            while j < len(lines) and lines[j].strip():
                found = float_re.findall(lines[j])
                if found:
                    probs.extend([float(x) for x in found])
                    if len(probs) >= 3 and len(probs) % 3 == 0:
                        j += 1
                        continue
                if not float_re.search(lines[j]):
                    break
                j += 1
            hints.append({"idx": idx, "move": move, "eq": eq, "probs": probs})
            i = j
        else:
            i += 1
    return hints

def process_mat_file(input_file, output_file):

    temp_script = random_filename()
    command_delay = 0.2
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

        parsed_moves = parse_backgammon_mat(content)
        augmented = process_game(parsed_moves)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(augmented, f, indent=2, ensure_ascii=False)

        # генерируем токены команд
        gnubg_tokens = json_to_gnubg_commands(augmented)
        logger.info([t["cmd"] for t in gnubg_tokens])

        # Инициализируем поле для подсказок в каждой записи
        for entry in augmented:
            entry.setdefault("hints", [])

        # Отправляем команды через pty с pexpect
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
                            augmented[target_idx]["hints"].append(h)
                    else:
                        logger.debug(
                            "No hints parsed for target %s, raw output length=%d",
                            target_idx,
                            len(out),
                        )
                        augmented[target_idx]["hints"].append({"raw": out})

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
                json.dump(augmented, f, indent=2, ensure_ascii=False)
            logger.info("Updated %s with hint data", output_file)
        except Exception:
            logger.exception("Failed to write augmented json with hints")
    finally:
        if os.path.exists(temp_script):
            os.remove(temp_script)