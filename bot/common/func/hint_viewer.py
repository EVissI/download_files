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
        if not line:
            continue

        # Проверяем победу (может быть с ведущими пробелами)
        win_match = re.match(r".*Wins (\d+) points", line)
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
        rest = num_match.group(2)  # keep spaces

        # Check for double in the line
        double_pos = rest.find("Doubles =>")
        if double_pos != -1:
            left = rest[:double_pos].strip()
            right = rest[double_pos + len("Doubles =>"):].strip()

            right_match = re.match(r"(\d+)(?:\s*(Takes|Drops|Take|Drop))?", right, re.I)
            if right_match:
                value = int(right_match.group(1))
                response = right_match.group(2).lower() if right_match.group(2) else None

                if left:
                    red_part = left
                    double_player = "Black"
                    red_move = parse_side(red_part, "Red") 
                    if red_move:
                        moves_list.append(red_move)
                        previous_player_moved = "Red"
                else:
                    double_player = "Red"

                moves_list.append({"turn": turn, "player": double_player, "action": "double", "cube": value, "gnu_move": " Double"})

                if response:
                    if response in ['take', 'takes']:
                        response = 'take'
                    elif response in ['drop', 'drops']:
                        response = 'drop'
                    response_player = "Red" if double_player == "Black" else "Black"
                    gnu_move = "take" if response == 'take' else 'pass'
                    moves_list.append({"turn": turn, "player": response_player, "action": response, "cube": value, "gnu_move": gnu_move})

            continue

        # Try split by large spaces
        parts = re.split(r'\s{10,}', rest)
        left = parts[0].strip() if len(parts) > 0 else ''
        right = parts[1].strip() if len(parts) > 1 else ''

        if len(parts) == 1:
            rest_single = rest.strip()
            dice_matches = list(re.finditer(r'(\d)(\d):', rest_single))
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
                dice_match_original = re.search(r'(\d)(\d):', rest)
                if dice_match_original:
                    dice_pos = dice_match_original.start()
                    pre_dice = rest[:dice_pos].strip()
                    post_dice = rest[dice_pos:].strip()
                    if pre_dice and re.match(r"(Takes|Drops|Take|Drop|Doubles)", pre_dice, re.I):
                        left = pre_dice
                        right = post_dice
                    else:
                        if turn == 1:
                            left = ''
                            right = post_dice
                        else:
                            left = post_dice
                            right = ''
            else:
                action_match_original = re.search(r'\S', rest)
                if action_match_original:
                    action_pos = action_match_original.start()
                    pre = rest[:action_pos].strip()
                    post = rest[action_pos:].strip()
                    if pre:
                        left = pre
                        right = post
                    else:
                        if turn == 1:
                            left = ''
                            right = post
                        else:
                            left = post
                            right = ''

        def parse_side(side_str, player):
            if not side_str:
                return None

            # Проверяем простые действия: Takes, Drops (независимо от регистра)
            action_match = re.match(r"(Takes|Drops|Take|Drop)", side_str, re.I)
            if action_match:
                act = action_match.group(1).lower()
                if act in ['take', 'takes']:
                    act = 'take'
                    gnu_move = 'take '
                elif act in ['drop', 'drops']:
                    act = 'drop'
                    gnu_move = 'pass'
                return {"turn": turn, "player": player, "action": act, "gnu_move": gnu_move}

            # Проверяем удвоение
            double_match = re.match(r"Doubles => (\d+)(?:\s*(Takes|Drops|Take|Drop))?", side_str, re.I)
            if double_match:
                value = int(double_match.group(1))
                res = {"turn": turn, "player": player, "action": "double", "cube": value, "gnu_move": " Double"}
                response = double_match.group(2)
                if response:
                    resp_act = response.lower()
                    if resp_act in ['take', 'takes']:
                        resp_act = 'take'
                        gnu_move_resp = 'take '
                    elif resp_act in ['drop', 'drops']:
                        resp_act = 'drop'
                        gnu_move_resp = 'pass'
                    # Добавляем ответ для противоположного игрока
                    resp_player = "Black" if player == "Red" else "Red"
                    actions = resp_act.split(',')
                    moves_list.append({"turn": turn, "player": resp_player, "action": resp_act, "cube": value, "gnu_move": gnu_move_resp})
                return res

            # Иначе парсим обычный ход
            dice_match = re.match(r"(\d)(\d):(?:\s*(.*))?", side_str)
            if dice_match:
                dice = [int(dice_match.group(1)), int(dice_match.group(2))]
                moves_str = dice_match.group(3) or ""
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
                return {"turn": turn, "player": player, "dice": dice, "moves": move_list}

            return None

        red_move = parse_side(left, "Red")
        if red_move:
            moves_list.append(red_move)
            previous_player_moved = "Red"

        black_move = parse_side(right, "Black")
        if black_move:
            moves_list.append(black_move)
            previous_player_moved = "Black"

        # Добавляем фиктивную запись для пропущенного хода (как в начале для Red)
        if not red_move and black_move:
            skip_entry = {"turn": turn, "player": "Red", "action": "skip"}
            moves_list.insert(-1 if black_move else len(moves_list), skip_entry)
        elif red_move and not black_move:
            skip_entry = {"turn": turn, "player": "Black", "action": "skip"}
            moves_list.append(skip_entry)

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

    i = 0
    while i < len(data):
        action = data[i]
        player = action.get("player")
        dice = action.get("dice")
        moves = action.get("moves", [])
        act = action.get("action")

        # Проверяем следующий ход в рамках того же turn
        next_act = None
        next_turn = None
        if i + 1 < len(data):
            next_act = data[i + 1].get("action")
            next_turn = data[i + 1].get("turn")

        if act == "skip":
            # Просто пропускаем, без команд
            i += 1
            continue
        elif act == "double":
            tokens.append({"cmd": "hint", "type": "hint", "target": i})
            tokens.append({"cmd": "double", "type": "cmd", "target": None})
            i += 1
            continue
        elif act in ("take", "drop"):
            tokens.append({"cmd": "hint", "type": "hint", "target": i})
            if act == "take":
                tokens.append({"cmd": "take", "type": "cmd", "target": None})
            if act == "drop":
                tokens.append({"cmd": 'pass', "type": "cmd", "target": None})
            i += 1
            continue
        elif act == "win":
            tokens.append({"cmd": "exit", "type": "cmd", "target": None})
            tokens.append({"cmd": "y", "type": "cmd", "target": None})
            i += 1
            continue
        elif dice:
            # Добавляем set dice и hint
            tokens.append(
                {"cmd": f"set dice {dice[0]}{dice[1]}", "type": "cmd", "target": i}
            )
            # Добавляем ходы, если есть
            if moves:
                tokens.append({"cmd": "hint", "type": "hint", "target": i})
                move_cmds = [f"{m['from']}/{m['to']}{'*' if m['hit'] else ''}" for m in moves]
                tokens.append({"cmd": " ".join(move_cmds), "type": "cmd", "target": i})
            # Добавляем roll только если следующий ход не double/takes/drop или в другом turn
            if not next_act or next_turn != action["turn"]:
                tokens.append({"cmd": "roll", "type": "cmd", "target": i})
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
                actions = action.split(",")
                action_1 = actions[0].strip()
                action_2 = actions[1].strip() if len(actions) > 1 else None
                equities.append({"idx": idx, "action_1": action_1,'action_2':action_2,  "eq": eq})

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
    Пример: "Peppa : 0                          Bbsm : 0"
    => ("Peppa", "Bbsm")
    """
    lines = content.splitlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("Game"):
            if i + 1 < len(lines):
                players_line = lines[i + 1].strip()
                # Находим все пары вида "Имя : число"
                matches = re.findall(r"(\S.*?)\s*:\s*\d+", players_line)
                if len(matches) >= 2:
                    red_player, black_player = matches[0].strip(), matches[1].strip()
                    logger.info(f"Extracted players: Red={red_player}, Black={black_player}")
                    return red_player, black_player

    logger.warning("Could not extract player names from .mat file")
    return "Red", "Black"

def normalize_move(move_str: str) -> str:
    """
    Нормализует строку хода: убирает пробелы, сортирует части для независимости от порядка,
    канонизирует позицию хита для эквивалентных ходов (e.g., "8/7* 13/7" == "13/7* 8/7").
    """
    moves = parse_gnu_move(move_str)
    if not moves:
        return ""

    # Convert to tuples (from, to, hit)
    move_tuples = [(m['from'], m['to'], m['hit']) for m in moves]

    # Sort by from desc, to desc, hit True first
    move_tuples.sort(key=lambda x: (-x[0], -x[1], -int(x[2])))

    # Canonicalize hits: collect per to
    hit_to = defaultdict(bool)
    for fr, to, hit in move_tuples:
        hit_to[to] |= hit

    # Assign hit to first move per to
    need_hit = set(to for to in hit_to if hit_to[to])
    new_tuples = []
    for fr, to, _ in move_tuples:
        hit = False
        if to in need_hit:
            hit = True
            need_hit.discard(to)
        new_tuples.append((fr, to, hit))

    # Rebuild moves list
    new_moves = [{'from': fr, 'to': to, 'hit': hit} for fr, to, hit in new_tuples]

    # Combine and return
    return convert_moves_to_gnu(new_moves) or ""

def parse_gnu_move(move_str: str):
    if not move_str:
        return []

    parts = move_str.split()
    moves = []
    for part in parts:
        hit = part.endswith('*')
        if hit:
            part = part[:-1]

        count = 1
        base = part
        if '(' in part and part.endswith(')'):
            base, count_str = part.rsplit('(', 1)
            count = int(count_str[:-1])

        segments = [s.lower() for s in base.split('/') if s]
        if not segments:
            continue

        fr_str = segments[0]
        fr = 25 if fr_str == 'bar' else int(fr_str) if fr_str.isdigit() else 0 if fr_str == 'off' else None
        if fr is None:
            continue

        for _ in range(count):
            prev = fr
            for seg in segments[1:]:
                to = 25 if seg == 'bar' else 0 if seg == 'off' else int(seg) if seg.isdigit() else None
                if to is None:
                    break
                moves.append({'from': prev, 'to': to, 'hit': False})
                prev = to

        if hit:
            if moves:
                moves[-1]['hit'] = True

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
    edges = defaultdict(int)            # (fr,to) -> count
    edge_hit = defaultdict(bool)        # (fr,to) -> True if any hit on that edge

    for m in moves_list:
        fr = m['from']
        to = m['to']
        edges[(fr, to)] += 1
        if m.get('hit'):
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
        candidate_starts = [a for (a, b), c in edges.items() if c > 0 and in_map.get(a, 0) == 0]
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
            next_edges = [(to, edges[(cur, to)]) for (fr, to) in edges.keys() if fr == cur and edges[(fr, to)] > 0]
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
    logger.debug(f"Converted to GNU: {final}")
    return final or None

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

def process_mat_file(input_file, output_file):
    temp_script = random_filename()
    command_delay = 0.5
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract player names before parsing moves
        red_player, black_player = extract_player_names(content)

        parsed_moves = parse_backgammon_mat(content)
        aug = process_game(parsed_moves)

        # Add player names to the output
        for entry in aug:
            if entry.get("player") == "Red":
                entry["player_name"] = red_player
            elif entry.get("player") == "Black":
                entry["player_name"] = black_player

        # Convert moves to GNU format
        for entry in aug:
            if "moves" in entry:
                entry["gnu_move"] = convert_moves_to_gnu(entry["moves"])

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(aug, f, indent=2, ensure_ascii=False)

        # генерируем токены команд
        gnubg_tokens = json_to_gnubg_commands(aug)
        logger.info([t["cmd"] for t in gnubg_tokens])

        # Инициализируем поле для подсказок в каждой записи
        for entry in aug:
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
                            aug[target_idx]["hints"].append(h)
                    else:
                        logger.debug(
                            "No hints parsed for target %s, raw output length=%d",
                            target_idx,
                            len(out),
                        )
                        aug[target_idx]["hints"].append({"raw": out})

            # Compare gnu_move with the first hint's move
            for entry in aug:
                if "gnu_move" in entry and entry.get("hints"):
                    # Find the first hint (idx == 1)
                    first_hint = next((hint for hint in entry["hints"] if hint.get("idx") == 1 and hint.get("type") == "move"), None)
                    if first_hint and "move" in first_hint:
                        # Нормализуем обе строки перед сравнением
                        normalized_gnu = normalize_move(entry["gnu_move"])
                        normalized_hint = normalize_move(first_hint["move"])
                        
                        entry["is_best_move"] = normalized_gnu == normalized_hint
                        
                        # Логирование для отладки
                        if not entry["is_best_move"]:
                            logger.debug(
                                "Move mismatch: gnu_move='{}' (normalized: '{}') vs hint='{}' (normalized: '{}')",
                                entry["gnu_move"], normalized_gnu, first_hint["move"], normalized_hint
                            )
                    else:
                        entry["is_best_move"] = False  # No valid first hint found
                        logger.warning("No valid first hint for entry: {}", entry)
                else:
                    entry["is_best_move"] = False  # No gnu_move or hints
                    logger.debug("Skipping comparison for entry without gnu_move or hints: {}", entry)

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
                json.dump(aug, f, indent=2, ensure_ascii=False)
            logger.info("Updated %s with hint data", output_file)
        except Exception:
            logger.exception("Failed to write augmented json with hints")
    finally:
        if os.path.exists(temp_script):
            os.remove(temp_script)