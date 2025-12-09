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
from concurrent.futures import ThreadPoolExecutor, as_completed
from multiprocessing import cpu_count

# ============================================================================
# === КОМПИЛИРУЕМ REGEX ОДИН РАЗ ===
# ============================================================================

REGEX_GAME = re.compile(r"^Game\s+(\d+)", re.MULTILINE)
REGEX_GAME_HEADER = re.compile(r"Game\s+(\d+)")
REGEX_PLAYERS = re.compile(r"(\S.*?)\s*:\s*(\d+)")
REGEX_MATCH_LENGTH = re.compile(r"(\d+)\s+point match")
REGEX_JACOBI = re.compile(r";Jacobi rule:\s*(True|False)", re.I)
REGEX_TURN = re.compile(r"(\d+)\)\s*(.*)", re.MULTILINE)
REGEX_WIN = re.compile(r".*Wins\s+(\d+)\s+points")
REGEX_DOUBLE = re.compile(r"Doubles\s+=>\s+(\d+)(?:\s*(Takes|Drops|Take|Drop))?", re.I)
REGEX_DOUBLE_MATCH = re.compile(r"Doubles => (\d+)(?:\s*(Takes|Drops|Take|Drop))?", re.I)
REGEX_DICE = re.compile(r"(\d)(\d):\s*(.*)?")
REGEX_ACTION = re.compile(r"(Takes|Drops|Take|Drop)", re.I)
REGEX_MOVE = re.compile(r"(\S+)/(\S+)")
REGEX_CLEAN_BACKSPACE = re.compile(r"[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]+")
REGEX_ENTRY = re.compile(
    r"^\s*(\d+)\.\s*(?:Cubeful\s+\d+-ply\s*)?(.*?)\s+Eq[:.]\s*([+-]?\d+(?:\.\d+)?)",
    re.IGNORECASE | re.MULTILINE
)
REGEX_FLOAT = re.compile(r"[+-]?\d*\.\d+")
REGEX_DOUBLE_POS = re.compile(r"Doubles =>")

# ============================================================================
# === КЭШИРОВАНИЕ РЕЗУЛЬТАТОВ ===
# ============================================================================

_game_cache = {}
_hint_cache = {}

# ============================================================================
# === ПЕРЕИСПОЛЬЗУЕМЫЙ ПУЛ GNUBG ПРОЦЕССОВ ===
# ============================================================================

class GnubgProcessPool:
    """Пул переиспользуемых gnubg процессов"""
    def __init__(self, pool_size=2):
        self.pool_size = pool_size
        self.processes = []
        self.available = []
        self.lock = threading.Lock()
        self._init_pool()
    
    def _init_pool(self):
        for i in range(self.pool_size):
            try:
                logger.info(f"Initializing gnubg process {i+1}/{self.pool_size}...")
                proc = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
                time.sleep(0.5)
                try:
                    proc.read_nonblocking(size=4096, timeout=0.2)
                except:
                    pass
                self.processes.append(proc)
                self.available.append(True)
                logger.info(f"✅ gnubg process {i+1} ready")
            except Exception as e:
                logger.error(f"Failed to spawn gnubg: {e}")
    
    def acquire(self):
        with self.lock:
            for i, avail in enumerate(self.available):
                if avail:
                    self.available[i] = False
                    return self.processes[i], i
        try:
            proc = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
            time.sleep(0.5)
            return proc, -1
        except Exception as e:
            logger.error(f"Failed to spawn fallback gnubg: {e}")
            return None, -1
    
    def release(self, proc_id):
        if proc_id >= 0 and proc_id < len(self.available):
            with self.lock:
                self.available[proc_id] = True
    
    def cleanup(self):
        for proc in self.processes:
            try:
                proc.close(force=True)
            except:
                pass
        logger.info("✅ gnubg pool cleaned up")


# ============================================================================
# === ИСПРАВЛЕННОЕ ЧТЕНИЕ ИЗ GNUBG ===
# ============================================================================

def read_gnubg_output(proc, timeout=0.5, max_attempts=10):
    """
    Улучшенное чтение вывода от gnubg.
    Ждет пока gnubg закончит писать в stdout.
    """
    out = ""
    attempts = 0
    empty_attempts = 0
    
    while attempts < max_attempts and empty_attempts < 2:
        try:
            chunk = proc.read_nonblocking(size=8192, timeout=timeout)
            if chunk:
                out += chunk
                empty_attempts = 0
            else:
                empty_attempts += 1
        except pexpect.TIMEOUT:
            empty_attempts += 1
        except pexpect.EOF:
            break
        except Exception as e:
            logger.debug(f"Read error: {e}")
            break
        
        attempts += 1
        time.sleep(0.05)
    
    return out


# ============================================================================
# === ПАРС ПОДСКАЗОК (ИСПРАВЛЕННЫЙ С ЛОГИРОВАНИЕМ) ===
# ============================================================================

def parse_hint_output(text: str, game_number: int = None):
    """Парсинг вывода подсказок от gnubg (ИСПРАВЛЕННЫЙ)"""
    def clean_text(s: str) -> str:
        if not s:
            return ""

        while "\x08" in s:
            i = s.find("\x08")
            if i <= 0:
                s = s[i + 1 :]
            else:
                s = s[: i - 1] + s[i + 1 :]

        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = REGEX_CLEAN_BACKSPACE.sub("", s)

        lines = []
        for ln in s.splitlines():
            ln_stripped = ln.strip()
            if not ln_stripped:
                continue

            low = ln_stripped.lower()

            if (
                low.startswith("hint")
                or low.startswith("considering")
                or "(black)" in low
                or "(red)" in low
            ):
                continue

            if re.match(r"^[\s\-=_\*\.]+$", ln_stripped):
                continue

            lines.append(ln.rstrip())

        return "\n".join(lines)

    cleaned = clean_text(text)
    
    # === ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ ===
    if game_number:
        logger.debug(f"Game {game_number} raw gnubg output ({len(text)} chars):")
        logger.debug(text[:500])
        logger.debug(f"After cleaning ({len(cleaned)} chars):")
        logger.debug(cleaned[:300])

    if not cleaned:
        logger.warning(f"Game {game_number}: No cleaned text from gnubg output")
        return []

    lines = [ln.rstrip() for ln in cleaned.splitlines()]

    # Проверяем кубовой анализ
    is_cube_analysis = any("Cube analysis" in line or "cube action" in line.lower() for line in lines)

    if is_cube_analysis:
        logger.info(f"Game {game_number}: Detected cube analysis")
        result = {"type": "cube_hint"}
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

        for line in lines:
            if "Proper cube action:" in line or "proper" in line.lower():
                result["prefer_action"] = line.split(":", 1)[1].strip() if ":" in line else ""
                break

        if equities:
            result["cubeful_equities"] = equities
            logger.info(f"Game {game_number}: Found {len(equities)} cube equities")

        return [result]

    # Парсинг обычных ходов
    hints = []
    i = 0

    while i < len(lines):
        m = REGEX_ENTRY.match(lines[i])
        if m:
            idx = int(m.group(1))
            move = m.group(2).strip()

            try:
                eq = float(m.group(3))
            except Exception:
                eq = 0.0

            probs = []
            j = i + 1

            while j < len(lines) and j < i + 5:
                line = lines[j].strip()
                if not line:
                    j += 1
                    continue

                found = REGEX_FLOAT.findall(line)
                if found:
                    probs.extend([float(x) for x in found])
                    j += 1
                else:
                    break

            hints.append({"type": "move", "idx": idx, "move": move, "eq": eq, "probs": probs})

            i = j
        else:
            i += 1

    if hints:
        logger.info(f"Game {game_number}: Parsed {len(hints)} move hints")

    return hints


# ============================================================================
# === ОСНОВНЫЕ ФУНКЦИИ ПАРСИНГА (скопированы из оригинала) ===
# ============================================================================

def parse_backgammon_mat(content):
    """Парсинг ходов из .mat файла"""
    lines = [
        line
        for line in content.splitlines()
        if line.strip() and not line.startswith(";") and "[" not in line
    ]

    start_idx = 0
    for i, line in enumerate(lines):
        if "Game" in line:
            start_idx = i + 2
            break

    moves_list = []
    for line in lines[start_idx:]:
        leading_spaces = len(line) - len(line.lstrip())
        line = line.strip()

        if not line:
            continue

        win_match = REGEX_WIN.match(line)
        if win_match:
            points = int(win_match.group(1))
            winner = "Red" if leading_spaces > 5 else "Black"
            moves_list.append({"action": "win", "player": winner, "points": points})
            continue

        num_match = re.match(r"(\d+)\)\s*(.*)", line)
        if not num_match:
            continue

        turn = int(num_match.group(1))
        rest = num_match.group(2)

        def parse_side(side_str, player):
            if not side_str:
                return None

            action_match = REGEX_ACTION.match(side_str)
            if action_match:
                act = action_match.group(1).lower()
                if act in ["take", "takes"]:
                    act = "take"
                    gnu_move = "take "
                elif act in ["drop", "drops"]:
                    act = "drop"
                    gnu_move = "pass"
                return {
                    "turn": turn,
                    "player": player,
                    "action": act,
                    "gnu_move": gnu_move,
                }

            double_match = REGEX_DOUBLE_MATCH.search(side_str)
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
                        gnu_move_resp = "take "
                    elif resp_act in ["drop", "drops"]:
                        resp_act = "drop"
                        gnu_move_resp = "pass"

                    resp_player = "Black" if player == "Red" else "Red"
                    moves_list.append({
                        "turn": turn,
                        "player": resp_player,
                        "action": resp_act,
                        "cube": value,
                        "gnu_move": gnu_move_resp,
                    })

                return res

            dice_match = REGEX_DICE.match(side_str)
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
                    if len(fr_to) < 2:
                        continue

                    try:
                        fr_str = fr_to[0]
                        fr = 25 if fr_str.lower() == "bar" else int(fr_str) if fr_str else None
                        to_str = fr_to[1]
                        to = 0 if to_str.lower() == "off" else int(to_str) if to_str else None

                        if fr is None or to is None:
                            continue

                        move_list.append({"from": fr, "to": to, "hit": hit})
                    except (ValueError, IndexError):
                        continue

                return {
                    "turn": turn,
                    "player": player,
                    "dice": dice,
                    "moves": move_list,
                }

            return None

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
                    double_player = "Red"
                    red_move = parse_side(red_part, "Black")
                    if red_move:
                        moves_list.append(red_move)
                else:
                    double_player = "Black"

                moves_list.append({
                    "turn": turn,
                    "player": double_player,
                    "action": "double",
                    "cube": value,
                    "gnu_move": "Double",
                })

                if response:
                    if response in ["take", "takes"]:
                        response = "take"
                    elif response in ["drop", "drops"]:
                        response = "drop"

                    response_player = "Black" if double_player == "Red" else "Red"
                    gnu_move = "take" if response == "take" else "pass"

                    moves_list.append({
                        "turn": turn,
                        "player": response_player,
                        "action": response,
                        "cube": value,
                        "gnu_move": gnu_move,
                    })

                continue

        parts = re.split(r"\s{10,}", rest)
        left = parts[0].strip() if len(parts) > 0 else ""
        right = parts[1].strip() if len(parts) > 1 else ""

        if len(parts) == 1:
            rest_single = rest.strip()
            dice_matches = list(re.finditer(r"(\d)(\d):", rest_single))

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
                dice_match_original = re.search(r"(\d)(\d):", rest)
                if dice_match_original:
                    dice_pos = dice_match_original.start()
                    pre_dice = rest[:dice_pos].strip()
                    post_dice = rest[dice_pos:].strip()

                    if pre_dice and re.match(r"(Takes|Drops|Take|Drop|Doubles)", pre_dice, re.I):
                        left = pre_dice
                        right = post_dice
                    else:
                        if turn == 1:
                            left = ""
                            right = post_dice
                        else:
                            left = post_dice
                            right = ""

        black_move = parse_side(left, "Black")
        if black_move:
            moves_list.append(black_move)

        red_move = parse_side(right, "Red")
        if red_move:
            moves_list.append(red_move)

        if not black_move and red_move:
            skip_entry = {"turn": turn, "player": "Black", "action": "skip"}
            moves_list.insert(-1 if red_move else len(moves_list), skip_entry)
        elif black_move and not red_move:
            skip_entry = {"turn": turn, "player": "Red", "action": "skip"}
            moves_list.append(skip_entry)

    return moves_list


def json_to_gnubg_commands(
    data,
    jacobi_rule=True,
    match_length=0,
    black_score=0,
    red_score=0,
    enable_crawford=False,
):
    """Конвертирует данные в команды gnubg"""
    jacoby_cmd = "set jacoby on" if jacobi_rule else "set jacoby off"
    tokens = [
        {"cmd": "set player 0 name Red", "type": "cmd", "target": None},
        {"cmd": "set player 1 name Black", "type": "cmd", "target": None},
        {"cmd": jacoby_cmd, "type": "cmd", "target": None},
        {"cmd": "set rng manual", "type": "cmd", "target": None},
        {"cmd": "set player 0 human", "type": "cmd", "target": None},
        {"cmd": "set player 1 human", "type": "cmd", "target": None},
    ]

    if match_length > 0:
        tokens.append({"cmd": f"new match {match_length}", "type": "cmd", "target": None})
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
            tokens.append({"cmd": f"set dice {dice[0]}{dice[1]}", "type": "cmd", "target": i})

            if black_score > 0 or red_score > 0:
                if match_length > 0:
                    if enable_crawford:
                        tokens.append({"cmd": f"set crawford on", "type": "cmd", "target": None})

                    tokens.append({
                        "cmd": f"set score {black_score} {red_score}",
                        "type": "cmd",
                        "target": None,
                    })
                    tokens.append({"cmd": f"y", "type": "cmd", "target": None})

            if skip_flag:
                tokens.append({"cmd": "roll", "type": "cmd", "target": i})
                tokens.append({
                    "cmd": f"set dice {dice[0]}{dice[1]}",
                    "type": "cmd",
                    "target": i,
                })
                skip_flag = False

            if moves:
                tokens.append({"cmd": "hint", "type": "hint", "target": i})
                move_cmds = [f"{m['from']}/{m['to']}{'*' if m['hit'] else ''}" for m in moves]
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


def extract_player_names(content: str) -> tuple:
    """Извлекает имена игроков из .mat файла"""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("Game"):
            if i + 1 < len(lines):
                players_line = lines[i + 1].strip()
                matches = REGEX_PLAYERS.findall(players_line)
                if len(matches) >= 2:
                    black_player, red_player = matches[0][0].strip(), matches[1][0].strip()
                    logger.info(f"Extracted players: Red={red_player}, Black={black_player}")
                    return red_player, black_player

    logger.warning("Could not extract player names from .mat file")
    return "Black", "Red"


def extract_match_length(content: str) -> int:
    """Извлекает длину матча из .mat файла"""
    for line in content.splitlines():
        match = REGEX_MATCH_LENGTH.search(line)
        if match:
            return int(match.group(1))

    logger.warning("Could not extract match length from .mat file")
    return 0


def extract_jacobi_rule(content: str) -> bool:
    """Извлекает правило Якоби из .mat файла"""
    for line in content.splitlines():
        match = REGEX_JACOBI.search(line)
        if match:
            return match.group(1).lower() == "true"

    logger.warning("Could not extract Jacobi rule from .mat file, defaulting to True")
    return True


def normalize_move(move_str: str) -> str:
    """Нормализует строку хода"""
    moves = parse_gnu_move(move_str)
    if not moves:
        return ""

    move_tuples = [(m["from"], m["to"], m["hit"]) for m in moves]
    move_tuples.sort(key=lambda x: (-x[0], -x[1], -int(x[2])))

    hit_to = defaultdict(bool)
    for fr, to, hit in move_tuples:
        hit_to[to] |= hit

    need_hit = set(to for to in hit_to if hit_to[to])
    new_tuples = []

    for fr, to, _ in move_tuples:
        hit = False
        if to in need_hit:
            hit = True
            need_hit.discard(to)

        new_tuples.append((fr, to, hit))

    new_moves = [{"from": fr, "to": to, "hit": hit} for fr, to, hit in new_tuples]
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
        fr = 25 if fr_str == "bar" else int(fr_str) if fr_str.isdigit() else (0 if fr_str == "off" else None)

        if fr is None:
            continue

        for _ in range(count):
            prev = fr
            for seg in segments[1:]:
                to = 25 if seg == "bar" else (0 if seg == "off" else (int(seg) if seg.isdigit() else None))

                if to is None:
                    break

                moves.append({"from": prev, "to": to, "hit": False})
                prev = to

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

    edges = defaultdict(int)
    edge_hit = defaultdict(bool)

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

        candidate_starts = [
            a for (a, b), c in edges.items() if c > 0 and in_map.get(a, 0) == 0
        ]

        if not candidate_starts:
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

        start = max(candidate_starts)

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
            single = None
            for (fr, to), cnt in edges.items():
                if cnt > 0 and fr == start:
                    single = (fr, to)
                    break

            if single is None:
                single = remaining[0][0]

            path = [single]

        counts = [edges[e] for e in path]
        k = min(counts)

        hits_per_edge = [edge_hit[e] for e in path]
        any_hit = any(hits_per_edge)
        middle_hits = any(hits_per_edge[:-1]) if len(hits_per_edge) > 1 else False
        last_edge_hit = hits_per_edge[-1]

        if len(path) == 1:
            fr, to = path[0]
            move_str = f"{fmt(fr)}/{fmt(to)}"
            if last_edge_hit:
                move_str += "*"
            if k > 1:
                move_str += f"({k})"
        else:
            if middle_hits:
                parts = [fmt(path[0][0])]
                for (fr, to), hit in zip(path, hits_per_edge):
                    landing = fmt(to)
                    if hit:
                        landing += "*"
                    parts.append(landing)

                move_str = "/".join(parts)

                if k > 1:
                    move_str += f"({k})"
            else:
                move_str = f"{fmt(path[0][0])}/{fmt(path[-1][1])}"
                if last_edge_hit:
                    move_str += "*"
                if k > 1:
                    move_str += f"({k})"

        result_parts.append(move_str)

        for e in path:
            edges[e] -= k
            if edges[e] <= 0:
                edges[e] = 0
                edge_hit[e] = False

    final = " ".join(result_parts)
    return final or None


class BackgammonPositionTracker:
    """Отслеживает позиции фишек на доске"""
    def __init__(self, invert_colors=False):
        self.invert_colors = invert_colors
        self.start_positions = {
            "red": {"bar": 0, "off": 0, 6: 5, 8: 3, 13: 5, 24: 2},
            "black": {"bar": 0, "off": 0, 1: 2, 12: 5, 17: 3, 19: 5},
        }
        self.reset()

    def reset(self):
        self.positions = copy.deepcopy(self.start_positions)
        self.current_player = "red" if not self.invert_colors else "black"

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

            if action:
                act = action.lower()

                if act == "skip":
                    e["positions"] = copy.deepcopy(self.positions)
                    e["inverted_positions"] = self._invert_positions(self.positions)
                    result.append(e)
                    continue

                elif act == "double":
                    pass

                elif act in ("take", "drop"):
                    self.current_player = "black" if self.current_player == "red" else "red"

                e["positions"] = copy.deepcopy(self.positions)
                e["inverted_positions"] = self._invert_positions(self.positions)
                result.append(e)
                continue

            moves = e.get("moves")
            if moves:
                for m in moves:
                    self.apply_move(player, m)

                self.current_player = "black" if player == "red" else "red"

            e["positions"] = copy.deepcopy(self.positions)
            e["inverted_positions"] = self._invert_positions(self.positions)
            result.append(e)

        return result

    def _invert_positions(self, positions):
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
    """Разбирает .mat файл на отдельные игры"""
    games = []
    lines = content.splitlines()
    current_game = None
    game_content = []
    red_player = None
    black_player = None
    red_score = None
    black_score = None

    for line in lines:
        if line.strip().startswith("Game"):
            if current_game is not None:
                games.append({
                    "game_number": current_game,
                    "red_player": red_player,
                    "black_player": black_player,
                    "red_score": red_score,
                    "black_score": black_score,
                    "content": "\n".join(game_content),
                })

            match = re.match(r"Game (\d+)", line.strip())
            if match:
                current_game = int(match.group(1))
                game_content = [line]
                red_player = None
                black_player = None
                red_score = None
                black_score = None

        elif current_game is not None:
            game_content.append(line)

            if ":" in line and not red_player:
                matches = REGEX_PLAYERS.findall(line)
                if len(matches) >= 2:
                    black_player, black_score = matches[0][0].strip(), int(matches[0][1])
                    red_player, red_score = matches[1][0].strip(), int(matches[1][1])

    if current_game is not None:
        games.append({
            "game_number": current_game,
            "red_player": red_player,
            "black_player": black_player,
            "red_score": red_score,
            "black_score": black_score,
            "content": "\n".join(game_content),
        })

    return games


# ============================================================================
# === ИСПРАВЛЕННЫЙ process_single_game (с логированием и улучшенным чтением) ===
# ============================================================================

def process_single_game(game_data, output_dir, game_number, gnubg_pool=None):
    """Обрабатывает одну игру (ИСПРАВЛЕННЫЙ)"""
    game_content = game_data["content"]
    red_player = game_data["red_player"]
    black_player = game_data["black_player"]

    parsed_moves = parse_backgammon_mat(game_content)
    tracker = BackgammonPositionTracker()
    aug = tracker.process_game(parsed_moves)

    for entry in aug:
        if entry.get("player") == "Red":
            entry["player_name"] = red_player
        elif entry.get("player") == "Black":
            entry["player_name"] = black_player

    for entry in aug:
        if "moves" in entry:
            entry["gnu_move"] = convert_moves_to_gnu(entry["moves"])

    gnubg_tokens = json_to_gnubg_commands(
        aug,
        game_data["jacobi_rule"],
        game_data["match_length"],
        game_data["black_score"],
        game_data["red_score"],
        game_data["enable_crawford"],
    )

    logger.info(f"Game {game_number}: Generated {len(gnubg_tokens)} tokens")

    for entry in aug:
        entry.setdefault("hints", [])
        entry.setdefault("cube_hints", [])

    # Используем gnubg пул если доступен
    if gnubg_pool:
        proc, proc_id = gnubg_pool.acquire()
    else:
        proc = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
        proc_id = -1

    command_delay = 0

    try:
        time.sleep(0.5)
        try:
            start_out = proc.read_nonblocking(size=4096, timeout=0.2)
        except Exception:
            pass

        for token_idx, token in enumerate(gnubg_tokens):
            line = token["cmd"]
            proc.sendline(line)
            time.sleep(command_delay)

            # Читаем обычный вывод
            out = read_gnubg_output(proc, timeout=0.3, max_attempts=3)

            if token["type"] in ("hint", "cube_hint"):
                target_idx = token.get("target")
                
                # ИСПРАВЛЕНИЕ: Больше времени для анализа
                time.sleep(3)  # вместо 2
                
                # Читаем результат анализа
                try:
                    hint_out = read_gnubg_output(proc, timeout=0.5, max_attempts=20)
                    if hint_out:
                        out += "\n" + hint_out
                except Exception as e:
                    logger.debug(f"Game {game_number}: Error reading hint output: {e}")

                # Парсим подсказку
                hints = parse_hint_output(out, game_number=game_number)
                if hints:
                    for h in hints:
                        if token["type"] == "cube_hint":
                            aug[target_idx]["cube_hints"].append(h)
                        elif token["type"] == "hint":
                            aug[target_idx]["hints"].append(h)
                    logger.info(f"Game {game_number} token {token_idx}: Got {len(hints)} hints")
                else:
                    logger.warning(f"Game {game_number} token {token_idx}: No hints parsed from gnubg")

        # Сравниваем ходы с подсказками
        for entry in aug:
            if "gnu_move" in entry and entry.get("hints"):
                first_hint = next(
                    (
                        hint
                        for hint in entry["hints"]
                        if hint.get("idx") == 1 and hint.get("type") == "move"
                    ),
                    None,
                )

                if first_hint and "move" in first_hint:
                    try:
                        normalized_gnu = normalize_move(entry["gnu_move"])
                        normalized_hint = normalize_move(first_hint["move"])
                        entry["is_best_move"] = normalized_gnu == normalized_hint
                    except Exception as e:
                        logger.warning(f"Game {game_number}: Error comparing moves: {e}")
                        entry["is_best_move"] = False
                else:
                    entry["is_best_move"] = False
            else:
                entry["is_best_move"] = False

        try:
            proc.sendline("exit")
            time.sleep(0.1)
            proc.sendline("y")
        except Exception:
            pass

        try:
            proc.expect(pexpect.EOF, timeout=10)
        except Exception:
            try:
                proc.close(force=True)
            except Exception:
                pass

    finally:
        try:
            if proc.isalive():
                proc.close(force=True)
        except Exception:
            pass

        if gnubg_pool:
            gnubg_pool.release(proc_id)

    # Сохраняем результат
    game_output_file = os.path.join(output_dir, f"game_{game_number:04d}.json")
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

    logger.info(f"✅ Game {game_number} processed and saved to {game_output_file}")

    return game_number, game_output_file  # Возвращаем для сортировки!


# ============================================================================
# === ИСПРАВЛЕННЫЙ process_mat_file (используем map вместо as_completed) ===
# ============================================================================

def process_mat_file(input_file, output_file, chat_id):
    """
    Основная функция обработки .mat файла.
    
    ИСПРАВЛЕНИЯ:
    1. Используем Executor.map() вместо as_completed() для сохранения порядка ✅
    2. Добавлено логирование для подсказок ✅
    3. Увеличены таймауты для gnubg анализа ✅
    4. Файлы с нулевым заполнением (game_0001.json вместо game_1.json) ✅
    """
    try:
        start_time = time.time()
        logger.info(f"Starting to process {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()

        games = parse_mat_games(content)

        if not games:
            raise ValueError("No games found in .mat file")

        first_game = games[0]
        red_player = first_game["red_player"]
        black_player = first_game["black_player"]
        red_score = first_game["red_score"]
        black_score = first_game["black_score"]

        match_length = extract_match_length(content)
        jacobi_rule = extract_jacobi_rule(content)

        crawford_game = None
        for game in games:
            if (
                game["black_score"] == match_length - 1
                or game["red_score"] == match_length - 1
            ):
                crawford_game = game["game_number"]
                break

        max_workers = min(4, len(games), cpu_count())
        logger.info(f"Using {max_workers} workers for {len(games)} games")

        gnubg_pool_size = max(1, max_workers // 2)
        gnubg_pool = GnubgProcessPool(pool_size=gnubg_pool_size)

        output_dir = output_file.rsplit(".", 1)[0] + "_games"
        os.makedirs(output_dir, exist_ok=True)

        games_to_process = []
        for game_data in games:
            game_data["match_length"] = match_length
            game_data["jacobi_rule"] = jacobi_rule
            game_data["enable_crawford"] = game_data["game_number"] == crawford_game
            games_to_process.append((game_data, output_dir, game_data["game_number"]))

        game_results = []

        logger.info("Starting parallel game processing...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            def process_game_wrapper(args):
                return process_single_game(args[0], args[1], args[2], gnubg_pool)
            
            # map() сохраняет порядок!
            for game_number, result_file in executor.map(process_game_wrapper, games_to_process):
                game_results.append({
                    "game_number": game_number,
                    "result_file": result_file,
                })
                elapsed = time.time() - start_time
                logger.info(f"✅ Game {game_number} completed ({elapsed:.1f}s elapsed)")

        gnubg_pool.cleanup()

        # Сортируем результаты
        game_results.sort(key=lambda x: x["game_number"])

        enable_crawford_game_number = crawford_game if crawford_game else None

        game_info = {
            "red_player": red_player,
            "black_player": black_player,
            "scores": {"Red": red_score, "Black": black_score},
            "match_length": match_length,
            "enable_crawford_game": enable_crawford_game_number,
            "jacobi_rule": jacobi_rule,
            "chat_id": str(chat_id),
            "total_games": len(games),
            "processed_games": len(game_results),
        }

        output_data = {"game_info": game_info, "games": game_results}

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        elapsed = time.time() - start_time
        logger.info(f"✅ Processed {len(game_results)}/{len(games)} games in {elapsed:.1f}s")
        if game_results:
            logger.info(f"   Average: {elapsed/len(game_results):.1f}s per game")
            logger.info(f"   Games saved to: {output_dir}")

    except Exception as e:
        logger.exception(f"Failed to process mat file {input_file}: {e}")
        raise