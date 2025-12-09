from collections import Counter, defaultdict
import copy
import functools
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

# ======================== КОМПИЛИРОВАННЫЕ REGEX ПАТТЕРНЫ ========================
# Это значительно ускоряет повторные совпадения в горячих циклах
REGEX_PATTERNS = {
    'num_match': re.compile(r'(\d+)\)\s*(.*)'),
    'win_match': re.compile(r'.*Wins (\d+) points'),
    'double_match': re.compile(r'Doubles => (\d+)(?:\s*(Takes|Drops|Take|Drop))?', re.I),
    'action_match': re.compile(r'(Takes|Drops|Take|Drop)', re.I),
    'dice_match': re.compile(r'(\d)(\d):(?:\s*(.*))?'),
    'double_check': re.compile(r'Doubles =>'),
    'dice_finditer': re.compile(r'(\d)(\d):'),
    'entry_re': re.compile(
        r'^\s*(\d+)\.\s*(?:Cubeful \d+-ply\s*)?(.*?)\s+Eq\.[:]?\s*([+-]?\\d+(?:\.\d+)?)',
        re.IGNORECASE
    ),
    'float_re': re.compile(r'[+-]?\d*\.\d+'),
    'backspace': re.compile(r'[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]+'),
    'game_header': re.compile(r'Game (\d+)'),
    'match_length': re.compile(r'(\d+)\s+point match'),
    'jacobi_rule': re.compile(r';Jacobi rule:\s*(True|False)', re.I),
    'player_extraction': re.compile(r'(\S.*?)\s*:\s*\d+'),
}

# ======================== ОПТИМИЗИРОВАННОЕ КОПИРОВАНИЕ ========================
def shallow_copy_positions(positions):
    """Поверхностное копирование позиций вместо глубокого."""
    return {k: dict(v) for k, v in positions.items()}

# ======================== КЭШИРОВАНИЕ ПАРСИНГА ========================
@functools.lru_cache(maxsize=256)
def _cached_parse_side_key(side_str: str, player: str):
    """Кэшированный парсинг для часто повторяемых ходов."""
    return side_str, player

# ======================== ОПТИМИЗИРОВАННОЕ ЛОГИРОВАНИЕ ========================
class OptimizedLogger:
    """Оборачивает logger для ленивого логирования."""
    _debug_enabled = None
    
    @classmethod
    def should_log_debug(cls):
        if cls._debug_enabled is None:
            cls._debug_enabled = logger.level <= 10  # DEBUG level
        return cls._debug_enabled
    
    @classmethod
    def debug_if_enabled(cls, msg):
        if cls.should_log_debug():
            logger.debug(msg)

opt_logger = OptimizedLogger()

# ======================== УЛУЧШЕННОЕ ЧТЕНИЕ ИЗ ПРОЦЕССА ========================
def read_output_from_process(proc, timeout=0.1, max_size=65536):
    """
    Унифицированное чтение вывода из процесса без избыточных попыток.
    """
    out = ""
    try:
        if proc.stdout is None:
            return out
        
        rlist, _, _ = select.select([proc.stdout], [], [], timeout)
        if rlist:
            chunk = proc.stdout.read(max_size)
            if chunk:
                out = chunk.decode('utf-8', errors='replace') if isinstance(chunk, bytes) else chunk
    except Exception as e:
        opt_logger.debug_if_enabled(f"Error reading process output: {e}")
    
    return out

# ======================== ОСНОВНАЯ ФУНКЦИЯ ПАРСИНГА ========================
def parse_backgammon_mat(content):
    """Оптимизированный парсинг .mat файла."""
    
    # Предварительно компилируем фильтры
    lines = [
        line for line in content.splitlines()
        if line.strip() and not line.startswith(";") and "[" not in line
    ]
    
    # Находим начало ходов
    start_idx = 0
    for i, line in enumerate(lines):
        if "Game" in line:
            start_idx = i + 2
            break
    
    moves_list = []
    
    for line in lines[start_idx:]:
        leading_spaces = len(line) - len(line.lstrip())
        line_stripped = line.strip()
        
        if not line_stripped:
            continue
        
        # Проверяем победу
        win_match = REGEX_PATTERNS['win_match'].match(line_stripped)
        if win_match:
            points = int(win_match.group(1))
            winner = "Red" if leading_spaces > 5 else "Black"
            moves_list.append({"action": "win", "player": winner, "points": points})
            continue
        
        # Проверяем номер хода
        num_match = REGEX_PATTERNS['num_match'].match(line_stripped)
        if not num_match:
            continue
        
        turn = int(num_match.group(1))
        rest = num_match.group(2)
        
        # Обработка основной логики хода
        _process_turn(turn, rest, moves_list)
    
    return moves_list

def _process_turn(turn, rest, moves_list):
    """Вспомогательная функция для обработки одного хода."""
    
    def parse_side(side_str, player):
        if not side_str:
            return None
        
        # Проверяем простые действия
        action_match = REGEX_PATTERNS['action_match'].match(side_str)
        if action_match:
            act = action_match.group(1).lower()
            if act in ["take", "takes"]:
                act = "take"
                gnu_move = "take "
            else:
                act = "drop"
                gnu_move = "pass"
            return {
                "turn": turn,
                "player": player,
                "action": act,
                "gnu_move": gnu_move,
            }
        
        # Проверяем удвоение
        double_match = REGEX_PATTERNS['double_match'].match(side_str)
        if double_match:
            value = int(double_match.group(1))
            res = {
                "turn": turn,
                "player": player,
                "action": "double",
                "cube": value,
                "gnu_move": "Double",
            }
            return res
        
        # Парсим обычный ход
        dice_match = REGEX_PATTERNS['dice_match'].match(side_str)
        if dice_match:
            dice = [int(dice_match.group(1)), int(dice_match.group(2))]
            moves_str = dice_match.group(3) or ""
            move_list = _parse_moves_from_string(moves_str)
            return {
                "turn": turn,
                "player": player,
                "dice": dice,
                "moves": move_list,
            }
        
        return None
    
    # Проверяем удвоение в строке
    if REGEX_PATTERNS['double_check'].search(rest):
        double_pos = rest.find("Doubles =>")
        left = rest[:double_pos].strip()
        right = rest[double_pos + len("Doubles =>"):].strip()
        
        right_match = REGEX_PATTERNS['double_match'].match(right)
        if right_match:
            value = int(right_match.group(1))
            response = right_match.group(2)
            
            if left:
                red_move = parse_side(left, "Black")
                if red_move:
                    moves_list.append(red_move)
            
            moves_list.append({
                "turn": turn,
                "player": "Red" if not left else "Black",
                "action": "double",
                "cube": value,
                "gnu_move": "Double",
            })
            
            if response:
                response_act = response.lower()
                response_act = "take" if response_act in ["take", "takes"] else "drop"
                moves_list.append({
                    "turn": turn,
                    "player": "Black" if not left else "Red",
                    "action": response_act,
                    "cube": value,
                    "gnu_move": "take" if response_act == "take" else "pass",
                })
            return
    
    # Разделяем по большим пробелам
    parts = re.split(r'\s{10,}', rest)
    left = parts[0].strip() if len(parts) > 0 else ""
    right = parts[1].strip() if len(parts) > 1 else ""
    
    if len(parts) == 1:
        rest_single = rest.strip()
        dice_matches = list(REGEX_PATTERNS['dice_finditer'].finditer(rest_single))
        
        if len(dice_matches) >= 2:
            _handle_two_dice_matches(dice_matches, rest_single, moves_list, parse_side, turn)
        elif len(dice_matches) == 1:
            _handle_one_dice_match(dice_matches[0], rest, moves_list, parse_side, turn)
        else:
            _handle_no_dice_matches(rest, moves_list, parse_side, turn)
    else:
        black_move = parse_side(left, "Black")
        if black_move:
            moves_list.append(black_move)
        
        red_move = parse_side(right, "Red")
        if red_move:
            moves_list.append(red_move)

def _parse_moves_from_string(moves_str):
    """Парсит строку ходов в список."""
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
            fr = 25 if fr_str.lower() == "bar" else int(fr_str)
            to_str = fr_to[1]
            to = 0 if to_str.lower() == "off" else int(to_str)
        except (ValueError, IndexError):
            continue
        
        move_list.append({"from": fr, "to": to, "hit": hit})
    
    return move_list

def _handle_two_dice_matches(dice_matches, rest_single, moves_list, parse_side, turn):
    """Обрабатывает случай с двумя dice."""
    red_dice_str = dice_matches[0].group(0)
    red_moves_start = dice_matches[0].end()
    red_moves_end = dice_matches[1].start()
    red_moves_str = rest_single[red_moves_start:red_moves_end].strip()
    left = f"{red_dice_str} {red_moves_str}".strip()
    
    black_dice_str = dice_matches[1].group(0)
    black_moves_start = dice_matches[1].end()
    black_moves_str = rest_single[black_moves_start:].strip()
    right = f"{black_dice_str} {black_moves_str}".strip()
    
    black_move = parse_side(left, "Black")
    if black_move:
        moves_list.append(black_move)
    
    red_move = parse_side(right, "Red")
    if red_move:
        moves_list.append(red_move)

def _handle_one_dice_match(dice_match, rest, moves_list, parse_side, turn):
    """Обрабатывает случай с одним dice."""
    dice_pos = dice_match.start()
    pre_dice = rest[:dice_pos].strip()
    post_dice = rest[dice_pos:].strip()
    
    if pre_dice and re.match(r'(Takes|Drops|Take|Drop|Doubles)', pre_dice, re.I):
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

def _handle_no_dice_matches(rest, moves_list, parse_side, turn):
    """Обрабатывает случай без dice."""
    action_match = re.search(r'\S', rest)
    if action_match:
        action_pos = action_match.start()
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
    else:
        left = ""
        right = rest
    
    black_move = parse_side(left, "Black")
    if black_move:
        moves_list.append(black_move)
    
    red_move = parse_side(right, "Red")
    if red_move:
        moves_list.append(red_move)

# ======================== ОСТАЛЬНЫЕ ФУНКЦИИ (С МИНИМАЛЬНЫМИ ИЗМЕНЕНИЯМИ) ========================

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
    """Генерирует команды для GNUBG с оптимизированной обработкой."""
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
            tokens.append({"cmd": "take" if act == "take" else "pass", "type": "cmd", "target": None})
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
                        tokens.append({"cmd": "set crawford on", "type": "cmd", "target": None})
                    tokens.append({
                        "cmd": f"set score {black_score} {red_score}",
                        "type": "cmd",
                        "target": None,
                    })
                    tokens.append({"cmd": "y", "type": "cmd", "target": None})
            
            if skip_flag:
                tokens.append({"cmd": "roll", "type": "cmd", "target": i})
                tokens.append({"cmd": f"set dice {dice[0]}{dice[1]}", "type": "cmd", "target": i})
                skip_flag = False
            
            if moves:
                tokens.append({"cmd": "hint", "type": "hint", "target": i})
                move_cmds = [f"{m['from']}/{m['to']}{'*' if m['hit'] else ''}" for m in moves]
                tokens.append({"cmd": " ".join(move_cmds), "type": "cmd", "target": i})
                tokens.append({"cmd": "hint", "type": "cube_hint", "target": i + 1})
        
        i += 1
    
    return tokens

def random_filename(ext=".gnubg", length=16):
    letters = string.ascii_letters + string.digits
    rand_str = "".join(random.choice(letters) for _ in range(length))
    return f"{rand_str}{ext}"

def parse_hint_output(text: str):
    """Оптимизированный парсинг вывода подсказок."""
    def clean_text(s: str) -> str:
        if not s:
            return ""
        
        # Удаляем backspace
        while "\x08" in s:
            i = s.find("\x08")
            s = s[: i - 1] + s[i + 1 :] if i > 0 else s[i + 1 :]
        
        # Нормализуем возвраты каретки
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        
        # Удаляем управляющие символы
        s = REGEX_PATTERNS['backspace'].sub("", s)
        
        lines = []
        for ln in s.splitlines():
            ln_stripped = ln.strip()
            if not ln_stripped:
                continue
            
            low = ln_stripped.lower()
            if (low.startswith("hint") or low.startswith("considering") or 
                "(black)" in low or "(red)" in low):
                continue
            
            if re.match(r"^[\s\-=_\*\.]+$", ln_stripped):
                continue
            
            lines.append(ln.rstrip())
        
        return "\n".join(lines)
    
    cleaned = clean_text(text)
    if not cleaned:
        return []
    
    lines = [ln.rstrip() for ln in cleaned.splitlines()]
    
    # Проверяем наличие анализа куба
    is_cube_analysis = any("Cube analysis" in line for line in lines)
    
    if is_cube_analysis:
        result = {"type": "cube_hint"}
        equities = []
        
        for line in lines:
            if match := re.match(
                r"(\d+)\.\s+(.*?)\s+([+-]?\d+\.\d+)(?:\s+\(([+-]?\d+\.\d+)\))?$", line
            ):
                idx = int(match.group(1))
                action = match.group(2).strip()
                eq = float(match.group(3))
                
                equities.append({
                    "idx": idx,
                    "action_1": action,
                    "action_2": None,
                    "eq": eq
                })
        
        for line in lines:
            if "Proper cube action:" in line:
                result["prefer_action"] = line.split("Proper cube action:", 1)[1].strip()
                break
        
        if equities:
            result["cubeful_equities"] = equities
        
        return [result]
    
    hints = []
    i = 0
    
    while i < len(lines):
        m = REGEX_PATTERNS['entry_re'].match(lines[i])
        if m:
            idx = int(m.group(1))
            move = m.group(2).strip()
            eq = float(m.group(3))
            
            probs = []
            j = i + 1
            while j < len(lines):
                line = lines[j].strip()
                if not line:
                    break
                
                found = REGEX_PATTERNS['float_re'].findall(line)
                if found:
                    probs.extend([float(x) for x in found])
                    j += 1
                    continue
                break
            
            hints.append({
                "type": "move",
                "idx": idx,
                "move": move,
                "eq": eq,
                "probs": probs
            })
            
            i = j
        else:
            i += 1
    
    return hints

def extract_player_names(content: str) -> tuple:
    """Извлекает имена игроков из .mat файла."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("Game"):
            if i + 1 < len(lines):
                players_line = lines[i + 1].strip()
                matches = REGEX_PATTERNS['player_extraction'].findall(players_line)
                if len(matches) >= 2:
                    return matches[1].strip(), matches[0].strip()
    
    logger.warning("Could not extract player names from .mat file")
    return "Red", "Black"

def extract_match_length(content: str) -> int:
    """Извлекает длину матча из .mat файла."""
    for line in content.splitlines():
        match = REGEX_PATTERNS['match_length'].match(line.strip())
        if match:
            return int(match.group(1))
    
    logger.warning("Could not extract match length from .mat file")
    return 0

def extract_jacobi_rule(content: str) -> bool:
    """Извлекает правило Якоби из .mat файла."""
    for line in content.splitlines():
        match = REGEX_PATTERNS['jacobi_rule'].match(line.strip())
        if match:
            return match.group(1).lower() == "true"
    
    logger.warning("Could not extract Jacobi rule from .mat file, defaulting to True")
    return True

def normalize_move(move_str: str) -> str:
    """Нормализует строку хода (кэшированная версия)."""
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
    """Парсит GNU формат хода."""
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
        
        if hit and moves:
            moves[-1]["hit"] = True
    
    return moves

def convert_moves_to_gnu(moves_list):
    """Конвертирует список ходов в GNU формат."""
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
    """Отслеживает позицию фишек на доске."""
    
    def __init__(self, invert_colors=False):
        self.invert_colors = invert_colors
        self.start_positions = {
            "red": {"bar": 0, "off": 0, 6: 5, 8: 3, 13: 5, 24: 2},
            "black": {"bar": 0, "off": 0, 1: 2, 12: 5, 17: 3, 19: 5},
        }
        self.reset()
    
    def reset(self):
        self.positions = shallow_copy_positions(self.start_positions)
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
                self.positions[side].pop(k, None)
    
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
                    pass
                elif act == "double":
                    pass
                elif act in ("take", "drop"):
                    self.current_player = "black" if self.current_player == "red" else "red"
                
                e["positions"] = shallow_copy_positions(self.positions)
                e["inverted_positions"] = self._invert_positions(self.positions)
                result.append(e)
                continue
            
            moves = e.get("moves")
            if moves:
                for m in moves:
                    self.apply_move(player, m)
                self.current_player = "black" if player == "red" else "red"
            
            e["positions"] = shallow_copy_positions(self.positions)
            e["inverted_positions"] = self._invert_positions(self.positions)
            result.append(e)
        
        return result
    
    def _invert_positions(self, positions):
        """Инвертирует позицию для другой ориентации доски."""
        inverted = {"red": {}, "black": {}}
        for color in ["red", "black"]:
            for key, value in positions[color].items():
                if key in ("bar", "off"):
                    inverted[color][key] = value
                else:
                    inverted_point = 25 - int(key)
                    inverted[color][str(inverted_point)] = value
        return inverted

def parse_mat_games(content):
    """Разбирает .mat файл на отдельные игры."""
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
            
            match = REGEX_PATTERNS['game_header'].match(line.strip())
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
                matches = REGEX_PATTERNS['player_extraction'].findall(line)
                if len(matches) >= 2:
                    black_player, black_score = matches[0], int(line.split(":")[-2].split()[-1])
                    red_player, red_score = matches[1], int(line.split(":")[-1].split()[0])
    
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

def estimate_processing_time(mat_file_path):
    """Оценивает время обработки .mat файла."""
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
            
            parsed_moves = parse_backgammon_mat(game_data["content"])
            tracker = BackgammonPositionTracker()
            aug = tracker.process_game(parsed_moves)
            
            gnubg_tokens = json_to_gnubg_commands(
                aug,
                game_data["jacobi_rule"],
                game_data["match_length"],
                game_data.get("black_score", 0),
                game_data.get("red_score", 0),
            )
            
            hint_count = sum(1 for token in gnubg_tokens if token["type"] in ("hint", "cube_hint"))
            estimated_time = hint_count * 2 + 10
            
            if estimated_time > max_estimated_time:
                max_estimated_time = estimated_time
        
        return max_estimated_time
    
    except Exception as e:
        logger.error(f"Error estimating processing time for {mat_file_path}: {e}")
        return 0

# ======================== ОСНОВНАЯ ОБРАБОТКА (ОПТИМИЗИРОВАНА ДЛЯ ПАРАЛЛЕЛИЗМА) ========================

def process_single_game(game_data, output_dir, game_number):
    """Обрабатывает одну игру с оптимизированным взаимодействием с GNUBG."""
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
    
    for entry in aug:
        entry.setdefault("hints", [])
        entry.setdefault("cube_hints", [])
    
    child = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
    
    try:
        time.sleep(0.5)
        _ = read_output_from_process(child, timeout=0.2)
        
        for token in gnubg_tokens:
            line = token["cmd"]
            child.sendline(line)
            time.sleep(0.1)  # Оптимизированный delay вместо зависимого от типа
            
            out = read_output_from_process(child, timeout=0.05)
            
            if token["type"] in ("hint", "cube_hint"):
                target_idx = token.get("target")
                time.sleep(1.5)  # Сокращено с 2 до 1.5
                
                chunk = read_output_from_process(child, timeout=0.1, max_size=65536)
                if chunk:
                    out += chunk
                
                hints = parse_hint_output(out)
                
                if hints:
                    for h in hints:
                        if token["type"] == "cube_hint":
                            aug[target_idx]["cube_hints"].append(h)
                        else:
                            aug[target_idx]["hints"].append(h)
        
        for entry in aug:
            if "gnu_move" in entry and entry.get("hints"):
                first_hint = next(
                    (hint for hint in entry["hints"] if hint.get("idx") == 1 and hint.get("type") == "move"),
                    None,
                )
                
                if first_hint and "move" in first_hint:
                    normalized_gnu = normalize_move(entry["gnu_move"])
                    normalized_hint = normalize_move(first_hint["move"])
                    entry["is_best_move"] = normalized_gnu == normalized_hint
                else:
                    entry["is_best_move"] = False
            else:
                entry["is_best_move"] = False
        
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
        
    finally:
        try:
            if child.isalive():
                child.close(force=True)
        except Exception:
            pass
    
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

def process_mat_file(input_file, output_file, chat_id):
    """Основная функция обработки .mat файла с параллелизмом."""
    try:
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
            if (game["black_score"] == match_length - 1 or 
                game["red_score"] == match_length - 1):
                crawford_game = game["game_number"]
                break
        
        output_dir = output_file.rsplit(".", 1)[0] + "_games"
        os.makedirs(output_dir, exist_ok=True)
        
        import concurrent.futures
        
        game_results = []
        enable_crawford_game_number = None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(games))) as executor:
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
                    game_results.append({
                        "game_number": game_number,
                        "result_file": result_file
                    })
                    logger.info(f"Game {game_number} processing completed")
                except Exception as e:
                    logger.error(f"Failed to process game {game_number}: {e}")
        
        game_info = {
            "red_player": red_player,
            "black_player": black_player,
            "scores": {"Red": red_score, "Black": black_score},
            "match_length": match_length,
            "enable_crawford_game": enable_crawford_game_number if crawford_game else None,
            "jacobi_rule": jacobi_rule,
            "chat_id": str(chat_id),
            "total_games": len(games),
            "processed_games": len(game_results),
        }
        
        output_data = {"game_info": game_info, "games": game_results}
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Processed {len(game_results)} games from {input_file}, saved to {output_file}")
    
    except Exception as e:
        logger.exception(f"Failed to process mat file {input_file}: {e}")
        raise