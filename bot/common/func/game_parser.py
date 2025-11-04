import os
import json
import re
from pathlib import Path
from typing import List, Dict, Union, Optional

Player = str  # 'first' or 'second'
Move = Dict[str, Union[int, str, List[int]]]
GameData = Dict[str, Union[Dict[str, Union[str, int]], int, List[Dict]]]


def toggle_player(player: Player) -> Player:
    return 'second' if player == 'first' else 'first'


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

        result.append({
            "move": move_number,
            "player1": player1_text,
            "player2": player2_text,
            "dice1": dice1,
            "dice2": dice2,
        })

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


def extract_moves(player_moves: str) -> List[Dict[str, Union[str, bool]]]:
    moves_list = []
    split_moves = player_moves.split(": ")
    if len(split_moves) == 1:
        return moves_list

    for move in split_moves[1].split(" "):
        if "/" not in move:
            continue
        start, end = move.split("/")
        captured = False
        if end.endswith("*"):
            captured = True
            end = end[:-1]
        moves_list.append({"from": start, "to": end, "captured": captured})

    return moves_list


def parse_game(text: str, points_match: Optional[int], is_long_game: bool, is_inverse: bool = False) -> GameData:
    lines = text.strip().split("\n")
    header_data = extract_names_and_scores(lines)

    first, second = ("second", "first") if is_inverse else ("first", "second")

    game_data = {
        first: {"name": header_data["first_name"], "score": header_data["first_score"]},
        second: {"name": header_data["second_name"], "score": header_data["second_score"]},
        "point_match": points_match,
        "is_long_game": is_long_game,
        "turns": [],
    }

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
                game_data["turns"].append({
                    "turn": player,
                    "dice": [0, 0],
                    "cube_owner": cube_owner,
                    "cube_value": cube_value,
                    "cube_location": cube_location,
                    "moves": [],
                    "action": "double",
                })
                continue

            if "Takes" in text_move:
                cube_location = player
                game_data["turns"].append({
                    "turn": player,
                    "dice": [0, 0],
                    "cube_owner": cube_owner,
                    "cube_value": cube_value,
                    "cube_location": cube_location,
                    "moves": [],
                    "action": "take",
                })
                continue

            if "Drops" in text_move:
                cube_location = None
                game_data["turns"].append({
                    "turn": player,
                    "dice": [0, 0],
                    "cube_owner": cube_owner,
                    "cube_value": cube_value,
                    "cube_location": cube_location,
                    "moves": [],
                    "action": "drop",
                })
                continue

            dice = move["dice1"] if player_key == "player1" else move["dice2"]
            moves_list = extract_moves(text_move)

            game_data["turns"].append({
                "turn": player,
                "dice": dice,
                "cube_owner": cube_owner,
                "cube_value": cube_value,
                "cube_location": cube_location,
                "moves": moves_list,
            })

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

    dir_path = Path("./front/public/json") / dir_name
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / "games.json"

    # Открываем файл для записи
    with open(file_path, "w", encoding="utf-8") as file:
        file.write("[")

        first = True
        count = 0

        for raw_game in games_raw:
            game = parse_game(raw_game, points_match, game_type, is_inverse)
            json_data = json.dumps(game, indent=2)

            if not first:
                file.write(",\n")
            file.write(json_data)
            first = False
            count += 1

        file.write("]")

    return count