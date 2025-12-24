import os
import json
import re
import copy
from pathlib import Path
from typing import List, Dict, Union, Optional

Player = str  # 'first' or 'second'
Move = Dict[str, Union[int, str, List[int]]]
GameData = Dict[str, Union[Dict[str, Union[str, int]], int, List[Dict]]]


class BackgammonPositionTracker:
    def __init__(self, invert_colors=False, is_long_game=False):
        self.invert_colors = invert_colors
        self.is_long_game = is_long_game
        # Set positions based on game type
        if self.is_long_game:
            self.start_positions = {
                "first": {"bar": 0, "off": 0, 6: 5, 8: 3, 13: 5, 23: 2, 24: 1},
                "second": {"bar": 0, "off": 0, 1: 1, 2: 2, 12: 5, 17: 3, 19: 5},
            }
        else:
            self.start_positions = {
                "first": {"bar": 0, "off": 0, 6: 5, 8: 3, 13: 5, 24: 2},
                "second": {"bar": 0, "off": 0, 1: 2, 12: 5, 17: 3, 19: 5},
            }
        self.reset()

    def reset(self):
        self.positions = copy.deepcopy(self.start_positions)
        self.current_player = (
            "first" if not self.invert_colors else "second"
        )  # first начинает, если не инвертировано

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
            if player == "first":
                fr = self.invert_point(fr)
                to = self.invert_point(to)
        else:
            if player == "second":
                fr = self.invert_point(fr)
                to = self.invert_point(to)

        key_fr, key_to = self._key(fr), self._key(to)
        opp = "first" if player == "second" else "second"

        self._dec(player, key_fr)

        if hit and key_to != "off":
            if self.positions[opp].get(key_to, 0) > 0:
                self._dec(opp, key_to)
                self._inc(opp, "bar")

        self._inc(player, key_to)

    def _invert_positions(self, positions):
        """Invert the positions for the board"""
        inverted = {"first": {}, "second": {}}
        for color in ["first", "second"]:
            for key, value in positions[color].items():
                if key == "bar" or key == "off":
                    inverted[color][key] = value
                else:
                    inverted_point = 25 - int(key)
                    inverted[color][str(inverted_point)] = value
        return inverted


def toggle_player(player: Player) -> Player:
    return "second" if player == "first" else "first"


def parse_move_table(lines: List[str]) -> List[Move]:
    result = []
    pattern = r"^\s*(\d+)\)\s*(.*?)\s{2,}(.*?)\s*$"

    for line in lines:
        line = line.rstrip()
        match = re.match(pattern, line)
        if not match:
            continue

        move_number = int(match[1])
        player1_text = match[2].strip()
        player2_text = match[3].strip()

        def extract_dice(s: str) -> List[int]:
            dice_match = re.match(r"^(\d{2}):", s)
            if dice_match:
                return [int(s[0]), int(s[1])]
            return []

        dice1 = extract_dice(player1_text)
        dice2 = extract_dice(player2_text)

        result.append(
            {
                "move": move_number,
                "player1": player1_text,
                "player2": player2_text,
                "dice1": dice1,
                "dice2": dice2,
            }
        )

    return result


def extract_names_and_scores(lines: List[str]) -> Dict[str, Union[str, int]]:
    pattern = r"^(.*?)\s*:\s*(\d+)\s+(.*?)\s*:\s*(\d+)\s*$"
    for line in lines:
        match = re.match(pattern, line)
        if match:
            return {
                "first_name": match[1].strip(),
                "first_score": int(match[2]),
                "second_name": match[3].strip(),
                "second_score": int(match[4]),
            }
    return {
        "first_name": "Player 1",
        "first_score": 0,
        "second_name": "Player 2",
        "second_score": 0,
    }


def extract_point_match(text: str) -> Optional[int]:
    pattern = r"(\d+)\s+point match"
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match[1]) if match else None


def extract_game_type(text: str) -> bool:
    return bool(re.search(r"Game type: Backgammon\s+\+1", text, re.IGNORECASE))


def extract_moves(player_moves: str) -> List[Dict[str, Union[int, bool]]]:
    moves_list = []
    split_moves = player_moves.split(": ")
    if len(split_moves) == 1:
        return moves_list

    for move in split_moves[1].split(" "):
        if "/" not in move:
            continue
        start, end = move.split("/")
        hit = False
        if end.endswith("*"):
            hit = True
            end = end[:-1]
        fr = 25 if start.lower() == "bar" else int(start)
        to = 0 if end.lower() == "off" else int(end)
        moves_list.append({"from": fr, "to": to, "hit": hit})

    return moves_list


def parse_game(
    text: str, points_match: Optional[int], is_long_game: bool, is_inverse: bool = False
) -> GameData:
    lines = text.strip().split("\n")
    header_data = extract_names_and_scores(lines)

    first, second = ("second", "first") if is_inverse else ("first", "second")

    # Найти информацию о победителе
    winner_info = None
    for line in reversed(lines):
        if "Wins" in line:
            wins_line = line
            break
    else:
        wins_line = None

    if wins_line:
        wins_match = re.search(r"Wins (\d+) points", wins_line)
        if wins_match:
            points = int(wins_match[1])
            leading_spaces = len(wins_line) - len(wins_line.lstrip())
            if leading_spaces <= 2:
                winner = first
            else:
                winner = second
            winner_info = {"player": winner, "points": points}

    game_data = {
        first: {"name": header_data["first_name"], "score": header_data["first_score"]},
        second: {
            "name": header_data["second_name"],
            "score": header_data["second_score"],
        },
        "point_match": points_match,
        "is_long_game": is_long_game,
        "is_crawford": False,
        "winner": winner_info,
        "turns": [],
    }

    tracker = BackgammonPositionTracker(
        invert_colors=is_inverse, is_long_game=is_long_game
    )
    tracker.reset()

    cube_owner = None
    cube_value = 1
    cube_location = None

    moves = parse_move_table(lines)

    for move in moves:
        for player_key in ["player1", "player2"]:
            player = first if player_key == "player1" else second
            text_move = move[player_key]
            if not text_move:
                continue

            if "Doubles =>" in text_move:
                cube_value = int(text_move.split("=>")[1].strip())
                cube_owner = toggle_player(player)
                cube_location = "center"
                game_data["turns"].append(
                    {
                        "turn": player,
                        "dice": [0, 0],
                        "cube_owner": cube_owner,
                        "cube_value": cube_value,
                        "cube_location": cube_location,
                        "moves": [],
                        "action": "double",
                    }
                )
                turn = game_data["turns"][-1]
                turn["positions"] = copy.deepcopy(tracker.positions)
                turn["inverted_positions"] = tracker._invert_positions(
                    tracker.positions
                )
                continue

            if "Takes" in text_move:
                cube_location = player
                game_data["turns"].append(
                    {
                        "turn": player,
                        "dice": [0, 0],
                        "cube_owner": cube_owner,
                        "cube_value": cube_value,
                        "cube_location": cube_location,
                        "moves": [],
                        "action": "take",
                    }
                )
                turn = game_data["turns"][-1]
                if turn["action"] in ("take", "drop"):
                    tracker.current_player = (
                        "second" if tracker.current_player == "first" else "first"
                    )
                turn["positions"] = copy.deepcopy(tracker.positions)
                turn["inverted_positions"] = tracker._invert_positions(
                    tracker.positions
                )
                continue

            if "Drops" in text_move:
                cube_location = None
                game_data["turns"].append(
                    {
                        "turn": player,
                        "dice": [0, 0],
                        "cube_owner": cube_owner,
                        "cube_value": cube_value,
                        "cube_location": cube_location,
                        "moves": [],
                        "action": "drop",
                    }
                )
                turn = game_data["turns"][-1]
                if turn["action"] in ("take", "drop"):
                    tracker.current_player = (
                        "second" if tracker.current_player == "first" else "first"
                    )
                turn["positions"] = copy.deepcopy(tracker.positions)
                turn["inverted_positions"] = tracker._invert_positions(
                    tracker.positions
                )
                continue

            dice = move["dice1"] if player_key == "player1" else move["dice2"]
            moves_list = extract_moves(text_move)

            game_data["turns"].append(
                {
                    "turn": player,
                    "dice": dice,
                    "cube_owner": cube_owner,
                    "cube_value": cube_value,
                    "cube_location": cube_location,
                    "moves": moves_list,
                }
            )
            turn = game_data["turns"][-1]
            if "moves" in turn and turn["moves"]:
                for m in turn["moves"]:
                    tracker.apply_move(turn["turn"], m)
                tracker.current_player = (
                    "second" if turn["turn"] == "first" else "first"
                )
            turn["positions"] = copy.deepcopy(tracker.positions)
            turn["inverted_positions"] = tracker._invert_positions(tracker.positions)

    return game_data


def get_names(data: str) -> List[str]:
    split_file = re.split(r"\n\nGame \d+\n", data)
    games_raw = split_file[1:]
    lines = games_raw[0].strip().split("\n")
    header_data = extract_names_and_scores(lines)
    return [header_data["first_name"], header_data["second_name"]]


async def parse_file(data: str, dir_name: str, is_inverse: bool = False) -> int:
    split_file = re.split(r"\n\nGame \d+\n", data)
    points_match = extract_point_match(split_file[0])
    game_type = extract_game_type(split_file[0])
    games_raw = split_file[1:]

    # Сначала парсим все игры в список
    games = []
    for raw_game in games_raw:
        game = parse_game(raw_game, points_match, game_type, is_inverse)
        games.append(game)

    # Определяем индекс игры Crawford
    crawford_index = None
    if points_match is not None:
        for i, game in enumerate(games):
            first_score = game["first"]["score"]
            second_score = game["second"]["score"]
            if max(first_score, second_score) == points_match - 1:
                crawford_index = i
                break

    # Добавляем флаг is_crawford, если найдена
    if crawford_index is not None:
        games[crawford_index]["is_crawford"] = True

    dir_path = Path("./files") / dir_name
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / "games.json"

    # Открываем файл для записи
    with open(file_path, "w", encoding="utf-8") as file:
        file.write("[")

        first = True
        count = 0

        for game in games:
            json_data = json.dumps(game, indent=2)

            if not first:
                file.write(",\n")
            file.write(json_data)
            first = False
            count += 1

        file.write("]")

    return count
