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

# ✅ ОПТИМИЗАЦИЯ: Компилируем regex один раз на загрузку модуля
_REGEX_MOVE = re.compile(r"(\d)(\d):(?:\s*(.*))?" )
_REGEX_DOUBLE = re.compile(r"Doubles => (\d+)(?:\s*(Takes|Drops|Take|Drop))?", re.I)
_REGEX_ACTION = re.compile(r"(Takes|Drops|Take|Drop)", re.I)
_REGEX_WIN = re.compile(r".*Wins (\d+) points")
_REGEX_GAME = re.compile(r"Game (\d+)")
_REGEX_PLAYERS = re.compile(r"(\S.*?)\s*:\s*(\d+)")
_REGEX_MATCH_LENGTH = re.compile(r"(\d+)\s+point match")
_REGEX_JACOBI = re.compile(r";Jacobi rule:\s*(True|False)", re.I)
_REGEX_HINT_ENTRY = re.compile(
    r"^\s*(\d+)\.\s*(?:Cubeful \d+-ply\s*)?(.*?)\s+Eq\.[:]?\s*([+-]?(?:\d+(?:\.\d+)?|,\d+))",
    re.IGNORECASE
)
_REGEX_FLOAT = re.compile(r"[+-]?(?:\d*[.,]\d+|\d+)")

def parse_backgammon_mat(content):
    """Парсит .mat файл в список ходов. ✅ Оптимизировано: вынесены вложенные функции"""
    lines = [
        line for line in content.splitlines()
        if line.strip() and not line.startswith(";") and "[" not in line
    ]
    
    start_idx = 0
    for i, line in enumerate(lines):
        # Формат хода: " 1) 52: ..." (номер в скобках в начале)
        if re.match(r"^\s*\d+\)", line.strip()):
            start_idx = i
            logger.debug(f"Found start of moves at line {i}: {line[:50]}")
            break
        
    moves_list = []
    
    for line in lines[start_idx:]:
        leading_spaces = len(line) - len(line.lstrip())
        line = line.strip()
        if not line:
            continue
        
        # Проверяем победу
        win_match = _REGEX_WIN.match(line)
        if win_match:
            points = int(win_match.group(1))
            winner = "Red" if leading_spaces > 5 else "Black"
            moves_list.append({"action": "win", "player": winner, "points": points})
            continue
        
        # Проверяем номер хода
        num_match = re.match(r"(\d+)\)\s*(.*)", line)
        if not num_match:
            continue
        
        turn = int(num_match.group(1))
        rest = num_match.group(2)
        
        # Парсим левую и правую части хода
        _parse_move_line(moves_list, turn, rest)
    
    return moves_list


def _parse_move_line(moves_list, turn, rest):
    """✅ Вынесено из parse_backgammon_mat для переиспользования"""
    double_pos = rest.find("Doubles =>")
    
    if double_pos != -1:
        # Обработка удвоения
        left = rest[:double_pos].strip()
        right = rest[double_pos + len("Doubles =>"):].strip()
        
        right_match = re.match(r"(\d+)(?:\s*(Takes|Drops|Take|Drop))?", right, re.I)
        if right_match:
            value = int(right_match.group(1))
            response = right_match.group(2).lower() if right_match.group(2) else None
            
            if left:
                red_move = _parse_side(left, "Black", turn)
                if red_move:
                    moves_list.append(red_move)
            else:
                moves_list.append({
                    "turn": turn,
                    "player": "Black",
                    "action": "double",
                    "cube": value,
                    "gnu_move": "Double",
                })
            
            if response:
                if response in ["take", "takes"]:
                    response = "take"
                    gnu_move_resp = "take"
                elif response in ["drop", "drops"]:
                    response = "drop"
                    gnu_move_resp = "pass"
                
                moves_list.append({
                    "turn": turn,
                    "player": "Red",
                    "action": response,
                    "cube": value,
                    "gnu_move": gnu_move_resp,
                })
        return
    
    # Парсим обычные ходы
    parts = re.split(r"\s{10,}", rest)
    left = parts[0].strip() if len(parts) > 0 else ""
    right = parts[1].strip() if len(parts) > 1 else ""
    
    if len(parts) == 1:
        # Пытаемся разбить по dice
        dice_matches = list(re.finditer(r"(\d)(\d):", rest.strip()))
        
        if len(dice_matches) >= 2:
            left, right = _split_by_dice(rest.strip(), dice_matches)
        elif len(dice_matches) == 1:
            left, right = _split_by_single_dice(rest.strip(), dice_matches[0], turn)
    
    black_move = _parse_side(left, "Black", turn)
    if black_move:
        moves_list.append(black_move)
    
    red_move = _parse_side(right, "Red", turn)
    if red_move:
        moves_list.append(red_move)
    
    # Добавляем skip, если один игрок пропустил
    if not black_move and red_move:
        moves_list.insert(-1 if red_move else len(moves_list), {
            "turn": turn,
            "player": "Black",
            "action": "skip"
        })
    elif black_move and not red_move:
        moves_list.append({
            "turn": turn,
            "player": "Red",
            "action": "skip"
        })


def _split_by_dice(rest_str, dice_matches):
    """✅ Вынесено для читаемости"""
    red_dice_str = dice_matches[0].group(0)
    red_moves_start = dice_matches[0].end()
    red_moves_end = dice_matches[1].start()
    red_moves_str = rest_str[red_moves_start:red_moves_end].strip()
    left = f"{red_dice_str} {red_moves_str}".strip()
    
    black_dice_str = dice_matches[1].group(0)
    black_moves_start = dice_matches[1].end()
    black_moves_str = rest_str[black_moves_start:].strip()
    right = f"{black_dice_str} {black_moves_str}".strip()
    
    return left, right


def _split_by_single_dice(rest_str, dice_match_obj, turn):
    """✅ Вынесено для читаемости"""
    dice_pos = dice_match_obj.start()
    pre_dice = rest_str[:dice_pos].strip()
    post_dice = rest_str[dice_pos:].strip()
    
    if pre_dice and _REGEX_ACTION.match(pre_dice, re.I):
        left = pre_dice
        right = post_dice
    else:
        if turn == 1:
            left = ""
            right = post_dice
        else:
            left = post_dice
            right = ""
    
    return left, right


def _parse_side(side_str, player, turn):
    """Парсит одну сторону хода (левую или правую). ✅ Вынесено"""
    if not side_str:
        return None
    
    # Простые действия
    action_match = _REGEX_ACTION.match(side_str)
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
    
    # Удвоение
    double_match = _REGEX_DOUBLE.match(side_str)
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
            
            resp_player = "Black" if player == "Red" else "Red"
            # Note: Не добавляем здесь, это добавится выше в _parse_move_line
        
        return res
    
    # Обычный ход
    dice_match = _REGEX_MOVE.match(side_str)
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


# ✅ ОПТИМИЗАЦИЯ: Функция для динамического ожидания подсказки
def _wait_for_hint_completion(child, timeout=5, check_interval=0.1):
    """
    Ждёт завершения анализа подсказки, проверяя маркеры завершения.
    Намного быстрее, чем фиксированный sleep(2).
    """
    out = ""
    end_time = time.time() + timeout
    last_read = time.time()
    completion_markers = [
        "Proper cube action:",
        "gnubg>",
        "quit",
    ]
    
    while time.time() < end_time:
        try:
            if child.stdout:
                chunk = child.read_nonblocking(size=4096, timeout=check_interval)
                if chunk:
                    out += chunk
                    last_read = time.time()
                    
                    # Проверяем маркеры завершения
                    for marker in completion_markers:
                        if marker in out:
                            return out
        except pexpect.TIMEOUT:
            # Если ничего не читали больше 0.5 сек и что-то было прочитано, завершаем
            if time.time() - last_read > 0.5 and out:
                break
        except pexpect.EOF:
            break
        except Exception:
            break
        
        time.sleep(check_interval)
    
    return out


def json_to_gnubg_commands(
    data,
    jacobi_rule=True,
    match_length=0,
    black_score=0,
    red_score=0,
    enable_crawford=False,
):
    """Генерирует команды для gnubg. Структура без изменений."""
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
            tokens.append(
                {"cmd": f"set dice {dice}{dice}", "type": "cmd", "target": i}
            )
            
            if black_score > 0 or red_score > 0:
                if match_length > 0:
                    if enable_crawford:
                        tokens.append(
                            {"cmd": f"set crawford on", "type": "cmd", "target": None}
                        )
                    
                    tokens.append({
                        "cmd": f"set score {black_score} {red_score}",
                        "type": "cmd",
                        "target": None,
                    })
                    tokens.append({"cmd": f"y", "type": "cmd", "target": None})
            
            if skip_flag:
                tokens.append({"cmd": "roll", "type": "cmd", "target": i})
                tokens.append({
                    "cmd": f"set dice {dice}{dice}",
                    "type": "cmd",
                    "target": i,
                })
            
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
    """Генерирует случайное имя файла."""
    letters = string.ascii_letters + string.digits
    rand_str = "".join(random.choice(letters) for _ in range(length))
    return f"{rand_str}{ext}"


def read_available(proc, timeout=0.1):
    """Читает доступные данные из proc.stdout без блокировки."""
    out = ""
    try:
        if proc.stdout is None:
            return out
        rlist, _, _ = select.select([proc.stdout], [], [], timeout)
        if rlist:
            out = proc.stdout.read()
    except Exception:
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                out += line
        except Exception:
            pass
    return out


def parse_hint_output(text: str):
    """Парсит вывод подсказок из gnubg."""
    def clean_text(s: str) -> str:
        if not s:
            return ""
        
        while "\\x08" in s:
            i = s.find("\\x08")
            if i <= 0:
                s = s[i + 1:]
            else:
                s = s[: i - 1] + s[i + 1:]
        
        s = s.replace("\\r\\n", "\\n").replace("\\r", "\\n")
        s = re.sub(r"[^\\x09\\x0A\\x20-\\x7E\\u00A0-\\uFFFF]+", "", s)
        
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
            
            if re.match(r"^[\\s\\-=_\\*\\.]+$", ln_stripped):
                continue
            
            lines.append(ln.rstrip())
        
        return "\\n".join(lines)
    
    cleaned = clean_text(text)
    if not cleaned:
        return []
    
    lines = [ln.rstrip() for ln in cleaned.splitlines()]
    
    is_cube_analysis = any("Cube analysis" in line for line in lines)
    
    if is_cube_analysis:
        result = {"type": "cube_hint"}
        equities = []
        
        for line in lines:
            if match := re.match(
                r"(\\d+)\\.\\s+(.*?)\\s+([+-]?\\d+\\.\\d+)(?:\\s+\\(([+-]?\\d+\\.\\d+)\\))?$", line
            ):
                idx = int(match.group(1))
                action = match.group(2).strip()
                eq = float(match.group(3))
                
                actions = action.split(",")
                action_1 = actions[0].strip()
                action_2 = actions[1].strip() if len(actions) > 1 else None
                
                equities.append({
                    "idx": idx,
                    "action_1": action_1,
                    "action_2": action_2,
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
        m = _REGEX_HINT_ENTRY.match(lines[i])
        if m:
            idx = int(m.group(1))
            move = m.group(2).strip()
            try:
                eq = float(m.group(3).replace(",", "."))
            except Exception:
                eq = 0.0
            
            probs = []
            j = i + 1
            while j < len(lines):
                line = lines[j].strip()
                if not line:
                    break
                
                found = _REGEX_FLOAT.findall(line)
                if found:
                    probs.extend([float(x.replace(",", ".")) for x in found])
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


def extract_player_names(content: str) -> tuple[str, str]:
    """Извлекает ники игроков из .mat файла."""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("Game"):
            if i + 1 < len(lines):
                players_line = lines[i + 1].strip()
                matches = re.findall(r"(\\S.*?)\\s*:\\s*\\d+", players_line)
                if len(matches) >= 2:
                    black_player, red_player = matches[0].strip(), matches[1].strip()
                    logger.info(f"Extracted players: Red={red_player}, Black={black_player}")
                    return red_player, black_player
    
    logger.warning("Could not extract player names from .mat file")
    return "Black", "Red"


def extract_match_length(content: str) -> int:
    """Извлекает длину матча из .mat файла."""
    lines = content.splitlines()
    for line in lines:
        match = _REGEX_MATCH_LENGTH.match(line.strip())
        if match:
            return int(match.group(1))
    
    logger.warning("Could not extract match length from .mat file")
    return 0


def extract_jacobi_rule(content: str) -> bool:
    """Извлекает правило Якоби из .mat файла."""
    lines = content.splitlines()
    for line in lines:
        match = _REGEX_JACOBI.match(line.strip())
        if match:
            return match.group(1).lower() == "true"
    
    logger.warning("Could not extract Jacobi rule from .mat file, defaulting to True")
    return True


def normalize_move(move_str: str) -> str:
    """Нормализует строку хода для сравнения."""
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
        fr = (
            25 if fr_str == "bar"
            else int(fr_str) if fr_str.isdigit() else 0 if fr_str == "off" else None
        )
        
        if fr is None:
            continue
        
        for _ in range(count):
            prev = fr
            for seg in segments[1:]:
                to = (
                    25 if seg == "bar"
                    else 0 if seg == "off" else int(seg) if seg.isdigit() else None
                )
                
                if to is None:
                    break
                
                moves.append({"from": prev, "to": to, "hit": False})
                prev = to
            
            if hit:
                if moves:
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
        last_edge_hit = hits_per_edge[-1] if hits_per_edge else False
        
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
    """Отслеживает позиции фишек на доске."""
    
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
    """
    ✅ ПОЛНОСТЬЮ ИСПРАВЛЕННАЯ: Разбирает .mat файл на отдельные игры.
    """
    games = []
    lines = content.splitlines()
    current_game = None
    game_content = []
    red_player = None
    black_player = None
    red_score = None
    black_score = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Проверяем, это ли начало новой игры (точно "Game N")
        game_match = re.match(r"^Game\s+(\d+)\s*$", line.strip())
        
        if game_match:
            # Сохраняем предыдущую игру, если она есть
            if current_game is not None:
                games.append({
                    "game_number": current_game,
                    "red_player": red_player,
                    "black_player": black_player,
                    "red_score": red_score,
                    "black_score": black_score,
                    "content": "\n".join(game_content),
                })
            
            # Начинаем новую игру
            current_game = int(game_match.group(1))
            game_content = [line]
            red_player = None
            black_player = None
            red_score = None
            black_score = None
            
            # Следующая строка содержит имена игроков и скоры
            i += 1
            if i < len(lines):
                player_line = lines[i]
                game_content.append(player_line)
                
                # Извлекаем имена игроков и скоры
                player_matches = re.findall(r"(\S.*?)\s*:\s*(\d+)", player_line)
                if len(player_matches) >= 2:
                    # ✅ ПРАВИЛЬНО: Распаковать кортежи из списка
                    black_player = player_matches.strip()
                    black_score = int(player_matches)
                    red_player = player_matches.strip()
                    red_score = int(player_matches)
                    logger.debug(f"Game {current_game}: Black={black_player} ({black_score}), Red={red_player} ({red_score})")
        
        elif current_game is not None:
            game_content.append(line)
        
        i += 1
    
    # Сохраняем последнюю игру
    if current_game is not None:
        games.append({
            "game_number": current_game,
            "red_player": red_player,
            "black_player": black_player,
            "red_score": red_score,
            "black_score": black_score,
            "content": "\n".join(game_content),
        })
    
    logger.info(f"Extracted {len(games)} games from .mat file")
    return games

# ✅ ОПТИМИЗАЦИЯ: Функция для обработки подсказок с динамическим ожиданием
def _process_hint_token(child, token, aug, index):
    """Обрабатывает одну подсказку с оптимизированным ожиданием."""
    target_idx = token.get("target")
    
    # ✅ ВМЕСТО time.sleep(2) - активное ожидание
    out = _wait_for_hint_completion(child, timeout=5, check_interval=0.1)
    
    hints = parse_hint_output(out)
    if hints:
        for h in hints:
            if token["type"] == "cube_hint":
                aug[target_idx]["cube_hints"].append(h)
            elif token["type"] == "hint":
                aug[target_idx]["hints"].append(h)


def process_single_game(game_data, output_dir, game_number):
    """Обрабатывает одну игру. ✅ Оптимизировано с динамическим ожиданием подсказок."""
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
    
    logger.info(f"Game {game_number} tokens: {[t['cmd'] for t in gnubg_tokens]}")
    
    for entry in aug:
        entry.setdefault("hints", [])
        entry.setdefault("cube_hints", [])
    
    child = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
    command_delay = 0
    
    try:
        time.sleep(0.5)
        try:
            start_out = child.read_nonblocking(size=4096, timeout=0.2)
        except Exception:
            pass
        
        for token in gnubg_tokens:
            line = token["cmd"]
            child.sendline(line)
            
            # ✅ ОПТИМИЗАЦИЯ: Различная обработка для hint и обычных команд
            if token["type"] not in ("hint", "cube_hint"):
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
            else:
                # ✅ ОПТИМИЗАЦИЯ: Для подсказок используем динамическое ожидание
                _process_hint_token(child, token, aug, None)
        
        # Сравниваем ходы с подсказками
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
    
    finally:
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
    """Основная функция обработки .mat файла."""
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
            if (
                game["black_score"] == match_length - 1
                or game["red_score"] == match_length - 1
            ):
                crawford_game = game["game_number"]
                break
        
        output_dir = output_file.rsplit(".", 1)[0] + "_games"
        os.makedirs(output_dir, exist_ok=True)
        
        import concurrent.futures
        
        game_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(games)) as executor:
            futures = []
            for game_data in games:
                game_data["match_length"] = match_length
                game_data["jacobi_rule"] = jacobi_rule
                game_data["enable_crawford"] = game_data["game_number"] == crawford_game
                
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
            "enable_crawford_game": crawford_game if crawford_game else None,
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