"""
Backgammon game hint viewer - FULLY REFACTORED AND TESTED
With all fixes for edge cases like test1.mat
"""

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
import concurrent.futures

from loguru import logger


# ============================================================================
# CONSTANTS
# ============================================================================

# Board constants
BAR_POSITION = 25
OFF_POSITION = 0
MIN_POINT = 1
MAX_POINT = 24
STANDARD_START_POSITIONS = {
    "red": {"bar": 0, "off": 0, 6: 5, 8: 3, 13: 5, 24: 2},
    "black": {"bar": 0, "off": 0, 1: 2, 12: 5, 17: 3, 19: 5},
}

# Parser patterns
GAME_HEADER_PATTERN = r"Game\s+(\d+)"
TURN_PATTERN = r"^(\d+)\)\s*(.*)"
WIN_PATTERN = r".*Wins\s+(\d+)\s+points"
DOUBLE_PATTERN = r"Doubles\s+=>"
DICE_PATTERN = r"(\d)(\d):"
PLAYER_SCORE_PATTERN = r"(\S.*?)\s*:\s*(\d+)"
MATCH_LENGTH_PATTERN = r"(\d+)\s+point\s+match"
JACOBI_RULE_PATTERN = r";Jacobi\s+rule:\s*(True|False)"
ACTION_PATTERN = r"(Takes|Drops|Take|Drop)"

# Action normalized forms
ACTION_TAKE = "take"
ACTION_DROP = "drop"
ACTION_DOUBLE = "double"
ACTION_SKIP = "skip"
ACTION_WIN = "win"
ACTION_MOVE = "move"

# Player colors
PLAYER_RED = "red"
PLAYER_BLACK = "black"

# Large space separator
LARGE_SPACE_SEP = r"\s{10,}"

# Timeouts and delays
GNUBG_TIMEOUT = 2
GNUBG_STARTUP_DELAY = 0.5
GNUBG_COMMAND_DELAY = 0
GNUBG_HINT_DELAY = 2
GNUBG_READ_TIMEOUT = 0.05
GNUBG_SHUTDOWN_TIMEOUT = 10
HINT_OUTPUT_BUFFER_SIZE = 65536
DICE_MATCHES_THRESHOLD = 2


# ============================================================================
# UTILITY FUNCTIONS - Text Processing
# ============================================================================

def normalize_action(action_str: str) -> str:
    """Normalize action strings (Take/Takes -> take, Drop/Drops -> drop)"""
    if not action_str:
        return None
    
    normalized = action_str.lower().strip()
    if normalized in ("take", "takes"):
        return ACTION_TAKE
    elif normalized in ("drop", "drops"):
        return ACTION_DROP
    return normalized


def get_gnu_move_for_action(action: str) -> str:
    """Convert action to GNU backgammon move command"""
    action = normalize_action(action)
    return "take" if action == ACTION_TAKE else "pass"


def position_to_string(position: int) -> str:
    """Convert board position to string representation"""
    if position == BAR_POSITION:
        return "bar"
    elif position == OFF_POSITION:
        return "off"
    return str(position)


def string_to_position(position_str: str) -> int:
    """Convert string position to integer"""
    pos_lower = position_str.lower()
    if pos_lower == "bar":
        return BAR_POSITION
    elif pos_lower == "off":
        return OFF_POSITION
    try:
        return int(position_str)
    except ValueError:
        return None


def get_opponent_player(player: str) -> str:
    """Get opponent of given player"""
    return PLAYER_BLACK if player == PLAYER_RED else PLAYER_RED


# ============================================================================
# UTILITY FUNCTIONS - Regex
# ============================================================================

def extract_match_value(pattern: str, text: str, group_idx: int = 1, data_type=str) -> any:
    """Generic pattern extractor with type conversion"""
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        try:
            return data_type(match.group(group_idx))
        except (ValueError, IndexError):
            return None
    return None


def find_all_dice_matches(text: str) -> list:
    """Find all dice patterns (e.g., '36:') in text"""
    return list(re.finditer(DICE_PATTERN, text))


def split_by_large_spaces(text: str) -> list:
    """Split text by 10+ consecutive spaces"""
    return re.split(LARGE_SPACE_SEP, text)


def extract_player_info(line: str) -> dict:
    """Extract player name and score from line like 'Name : score'"""
    matches = re.findall(PLAYER_SCORE_PATTERN, line)
    if len(matches) >= 2:
        return {
            "first_player": matches[0][0].strip(),
            "first_score": int(matches[0][1]),
            "second_player": matches[1][0].strip(),
            "second_score": int(matches[1][1]),
        }
    return None


# ============================================================================
# MOVE PARSING
# ============================================================================

class MoveParser:
    """Handles parsing individual moves from text"""
    
    @staticmethod
    def parse_single_move(move_text: str) -> dict:
        """Parse single move like '6/2' or 'bar/24*' or 'off'"""
        if not move_text:
            return None
        
        move_text = move_text.strip()
        has_hit = move_text.endswith("*")
        if has_hit:
            move_text = move_text[:-1]
        
        segments = move_text.split("/")
        if len(segments) < 2:
            return None
        
        from_pos = string_to_position(segments[0])
        to_pos = string_to_position(segments[1])
        
        if from_pos is None or to_pos is None:
            return None
        
        return {
            "from": from_pos,
            "to": to_pos,
            "hit": has_hit,
        }
    
    @staticmethod
    def parse_moves_from_string(moves_str: str) -> list:
        """Parse multiple moves from space-separated string"""
        if not moves_str:
            return []
        
        moves = []
        for move_text in moves_str.split():
            parsed_move = MoveParser.parse_single_move(move_text)
            if parsed_move:
                moves.append(parsed_move)
        
        return moves
    
    @staticmethod
    def parse_dice_and_moves(side_str: str) -> dict:
        """Parse dice notation and moves: '36: 13/10 10/4'"""
        if not side_str:
            return None
        
        dice_match = re.match(r"(\d)(\d):\s*(.*)?", side_str)
        if not dice_match:
            return None
        
        dice = [int(dice_match.group(1)), int(dice_match.group(2))]
        moves_str = dice_match.group(3) or ""
        moves = MoveParser.parse_moves_from_string(moves_str)
        
        return {
            "dice": dice,
            "moves": moves,
        }


# ============================================================================
# POSITION TRACKING
# ============================================================================

class BackgammonPositionTracker:
    """Track board position throughout game"""
    
    def __init__(self, invert_colors: bool = False):
        self.invert_colors = invert_colors
        self.positions = copy.deepcopy(STANDARD_START_POSITIONS)
        self.current_player = (
            PLAYER_BLACK if invert_colors else PLAYER_RED
        )
    
    @staticmethod
    def invert_point(point: int) -> int:
        """Invert point for rotated board"""
        if point in (OFF_POSITION, BAR_POSITION):
            return point
        return BAR_POSITION - point
    
    def _position_key(self, position: int) -> str:
        """Convert position to storage key"""
        return position_to_string(position)
    
    def _decrement_position(self, player: str, position_key: str) -> None:
        """Remove one checker from position"""
        current = self.positions[player].get(position_key, 0)
        if current > 1:
            self.positions[player][position_key] = current - 1
        elif current == 1:
            self.positions[player].pop(position_key, None)
        else:
            logger.debug(f"Warning: removing from empty position {position_key}")
    
    def _increment_position(self, player: str, position_key: str) -> None:
        """Add one checker to position"""
        self.positions[player][position_key] = self.positions[player].get(position_key, 0) + 1
    
    def apply_move(self, player: str, move: dict) -> None:
        """Apply single move to position"""
        from_pos = move.get("from")
        to_pos = move.get("to")
        is_hit = move.get("hit", False)
        
        # Apply board inversion if needed
        if self.invert_colors and player == PLAYER_RED:
            from_pos = self.invert_point(from_pos)
            to_pos = self.invert_point(to_pos)
        elif self.invert_colors and player == PLAYER_BLACK:
            from_pos = self.invert_point(from_pos)
            to_pos = self.invert_point(to_pos)
        
        from_key = self._position_key(from_pos)
        to_key = self._position_key(to_pos)
        opponent = get_opponent_player(player)
        
        self._decrement_position(player, from_key)
        
        if is_hit and to_key != "off":
            opponent_count = self.positions[opponent].get(to_key, 0)
            if opponent_count > 0:
                self._decrement_position(opponent, to_key)
                self._increment_position(opponent, "bar")
        
        self._increment_position(player, to_key)
    
    def process_game(self, moves_data: list) -> list:
        """Process entire game and augment with positions"""
        self.positions = copy.deepcopy(STANDARD_START_POSITIONS)
        result = []
        
        for entry in moves_data:
            entry_copy = copy.deepcopy(entry)
            action = entry_copy.get("action")
            player = entry_copy.get("player", self.current_player).lower()
            
            # Handle special actions
            if action == ACTION_SKIP:
                self._add_positions_to_entry(entry_copy)
                result.append(entry_copy)
                continue
            
            elif action == ACTION_DOUBLE:
                # Doubling doesn't change positions
                pass
            
            elif action in (ACTION_TAKE, ACTION_DROP):
                self.current_player = get_opponent_player(self.current_player)
                self._add_positions_to_entry(entry_copy)
                result.append(entry_copy)
                continue
            
            # Handle normal moves
            moves = entry_copy.get("moves", [])
            if moves:
                for move in moves:
                    self.apply_move(player, move)
                self.current_player = get_opponent_player(player)
            
            self._add_positions_to_entry(entry_copy)
            result.append(entry_copy)
        
        return result
    
    def _add_positions_to_entry(self, entry: dict) -> None:
        """Add current positions to entry"""
        entry["positions"] = copy.deepcopy(self.positions)
        entry["inverted_positions"] = self._invert_positions_dict(self.positions)
    
    def _invert_positions_dict(self, positions: dict) -> dict:
        """Create inverted board positions"""
        inverted = {PLAYER_RED: {}, PLAYER_BLACK: {}}
        
        for color in [PLAYER_RED, PLAYER_BLACK]:
            for key, value in positions[color].items():
                if key in ("bar", "off"):
                    inverted[color][key] = value
                else:
                    inverted_point = BAR_POSITION - int(key)
                    inverted[color][str(inverted_point)] = value
        
        return inverted


# ============================================================================
# MAT FILE PARSING
# ============================================================================

class MatFileParser:
    """Parse GNU Backgammon .mat files"""
    
    @staticmethod
    def extract_game_header(content: str) -> dict:
        """Extract match info from header"""
        return {
            "match_length": extract_match_value(MATCH_LENGTH_PATTERN, content, 1, int) or 0,
            "jacobi_rule": extract_match_value(JACOBI_RULE_PATTERN, content, 1) == "True",
        }
    
    @staticmethod
    def clean_lines(content: str) -> list:
        """Remove empty lines, comments, metadata"""
        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(";") and "[" not in line:
                lines.append(line)
        return lines
    
    @staticmethod
    def find_game_start_index(lines: list) -> int:
        """Find where game moves begin"""
        for i, line in enumerate(lines):
            if "Game" in line:
                return i + 2  # Skip game header and score line
        return 0
    
    @staticmethod
    def parse_games(content: str) -> list:
        """Split .mat file into individual games"""
        games = []
        lines = content.splitlines()
        current_game_number = None
        game_content = []
        player_info = None
        
        for line in lines:
            if line.strip().startswith("Game"):
                # Save previous game
                if current_game_number is not None:
                    games.append({
                        "game_number": current_game_number,
                        "player_info": player_info,
                        "content": "\n".join(game_content),
                    })
                
                # Start new game
                match = re.match(GAME_HEADER_PATTERN, line.strip())
                if match:
                    current_game_number = int(match.group(1))
                    game_content = [line]
                    player_info = None
            
            elif current_game_number is not None:
                game_content.append(line)
                
                # Extract player info
                if ":" in line and not player_info:
                    player_info = extract_player_info(line)
        
        # Save last game
        if current_game_number is not None:
            games.append({
                "game_number": current_game_number,
                "player_info": player_info,
                "content": "\n".join(game_content),
            })
        
        return games


# ============================================================================
# GNUBG INTEGRATION
# ============================================================================

class GnuBackgammonCommandGenerator:
    """Generate command tokens for GNU Backgammon"""
    
    @staticmethod
    def generate_tokens(
        moves_data: list,
        jacobi_rule: bool = True,
        match_length: int = 0,
        black_score: int = 0,
        red_score: int = 0,
    ) -> list:
        """Generate command tokens for GNUBG execution"""
        tokens = []
        
        # Setup commands
        tokens.extend([
            {"cmd": "set player 0 name Red", "type": "cmd", "target": None},
            {"cmd": "set player 1 name Black", "type": "cmd", "target": None},
            {"cmd": f"set jacoby {'on' if jacobi_rule else 'off'}", "type": "cmd", "target": None},
            {"cmd": "set rng manual", "type": "cmd", "target": None},
            {"cmd": "set player 0 human", "type": "cmd", "target": None},
            {"cmd": "set player 1 human", "type": "cmd", "target": None},
        ])
        
        # Match setup
        if match_length > 0:
            tokens.append({"cmd": f"new match {match_length}", "type": "cmd", "target": None})
        else:
            tokens.append({"cmd": "new game", "type": "cmd", "target": None})
        
        # Process moves
        for i, move_entry in enumerate(moves_data):
            GnuBackgammonCommandGenerator._add_move_tokens(
                tokens, move_entry, i, black_score, red_score
            )
        
        # Cleanup
        tokens.extend([
            {"cmd": "exit", "type": "cmd", "target": None},
            {"cmd": "y", "type": "cmd", "target": None},
        ])
        
        return tokens
    
    @staticmethod
    def _add_move_tokens(tokens: list, move_entry: dict, index: int, 
                        black_score: int, red_score: int) -> None:
        """Add tokens for single move"""
        action = move_entry.get("action")
        dice = move_entry.get("dice")
        moves = move_entry.get("moves", [])
        
        if action == ACTION_SKIP:
            return
        
        elif action == ACTION_DOUBLE:
            tokens.append({"cmd": "hint", "type": "cube_hint", "target": index})
            tokens.append({"cmd": "double", "type": "cmd", "target": None})
        
        elif action in (ACTION_TAKE, ACTION_DROP):
            tokens.append({"cmd": "hint", "type": "cube_hint", "target": index})
            cmd = "take" if action == ACTION_TAKE else "pass"
            tokens.append({"cmd": cmd, "type": "cmd", "target": None})
        
        elif action == ACTION_WIN:
            # Already added exit commands
            pass
        
        elif dice:
            tokens.append({"cmd": "roll", "type": "cmd", "target": index})
            tokens.append({
                "cmd": f"set dice {dice[0]}{dice[1]}",
                "type": "cmd",
                "target": index,
            })
            
            if black_score > 0 or red_score > 0:
                tokens.append({
                    "cmd": f"set score {black_score} {red_score}",
                    "type": "cmd",
                    "target": None,
                })
                tokens.append({"cmd": "y", "type": "cmd", "target": None})
            
            if moves:
                tokens.append({"cmd": "hint", "type": "hint", "target": index})
                move_strs = [
                    f"{m['from']}/{m['to']}{'*' if m['hit'] else ''}"
                    for m in moves
                ]
                tokens.append({
                    "cmd": " ".join(move_strs),
                    "type": "cmd",
                    "target": index,
                })
                tokens.append({"cmd": "hint", "type": "cube_hint", "target": index + 1})


# ============================================================================
# OUTPUT PARSING
# ============================================================================

class HintOutputParser:
    """Parse GNUBG hint output"""
    
    @staticmethod
    def parse(text: str) -> list:
        """Parse hint output into structured hints"""
        cleaned = HintOutputParser._clean_output(text)
        if not cleaned:
            return []
        
        lines = [line.rstrip() for line in cleaned.splitlines()]
        
        # Check for cube analysis
        if any("Cube analysis" in line for line in lines):
            return HintOutputParser._parse_cube_hints(lines)
        
        return HintOutputParser._parse_move_hints(lines)
    
    @staticmethod
    def _clean_output(text: str) -> str:
        """Clean GNUBG output"""
        if not text:
            return ""
        
        # Handle backspace
        while "\x08" in text:
            i = text.find("\x08")
            text = text[:max(0, i - 1)] + text[i + 1:]
        
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Remove control characters
        text = re.sub(r"[^\x09\x0A\x20-\x7E\u00A0-\uFFFF]+", "", text)
        
        # Filter lines
        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            
            lower = stripped.lower()
            if any(s in lower for s in ["hint", "considering", "(black)", "(red)"]):
                continue
            
            if re.match(r"^[\s\-=_\*\.]+$", stripped):
                continue
            
            lines.append(line.rstrip())
        
        return "\n".join(lines)
    
    @staticmethod
    def _parse_cube_hints(lines: list) -> list:
        """Parse cube analysis hints"""
        result = {"type": "cube_hint"}
        equities = []
        
        for line in lines:
            match = re.match(
                r"(\d+)\.\s+(.*?)\s+([+-]?\d+\.\d+)(?:\s+\(([+-]?\d+\.\d+)\))?$",
                line
            )
            if match:
                equities.append({
                    "idx": int(match.group(1)),
                    "action": match.group(2).strip(),
                    "equity": float(match.group(3)),
                })
            
            if "Proper cube action:" in line:
                result["preferred_action"] = line.split("Proper cube action:", 1)[1].strip()
        
        if equities:
            result["equities"] = equities
        
        return [result]
    
    @staticmethod
    def _parse_move_hints(lines: list) -> list:
        """Parse move analysis hints"""
        hints = []
        entry_pattern = re.compile(
            r"^\s*(\d+)\.\s*(?:Cubeful \d+-ply\s*)?(.*?)\s+Eq\.[:]*\s*([+-]?\d+(?:\.\d+)?)",
            re.IGNORECASE,
        )
        
        i = 0
        while i < len(lines):
            match = entry_pattern.match(lines[i])
            if match:
                idx = int(match.group(1))
                move = match.group(2).strip()
                try:
                    equity = float(match.group(3))
                except ValueError:
                    equity = 0.0
                
                # Collect probabilities from following lines
                probs = []
                j = i + 1
                while j < len(lines):
                    line = lines[j].strip()
                    if not line:
                        break
                    found = re.findall(r"[+-]?\d*\.\d+", line)
                    probs.extend(float(x) for x in found)
                    j += 1
                
                hints.append({
                    "type": "move",
                    "idx": idx,
                    "move": move,
                    "equity": equity,
                    "probabilities": probs,
                })
                i = j
            else:
                i += 1
        
        return hints


# ============================================================================
# GAME PARSING CLASSES - WITH ALL FIXES
# ============================================================================

class GameActionParser:
    """Parse and categorize individual game actions"""
    
    @staticmethod
    def parse_win_action(line: str, previous_player: str, moves_history: list) -> dict:
        """Parse win/game end action"""
        points_match = re.match(WIN_PATTERN, line)
        if not points_match:
            return None
        
        points = int(points_match.group(1))
        
        # If last action was drop, winner is opponent of player who dropped
        if moves_history and moves_history[-1].get("action") == ACTION_DROP:
            winner = get_opponent_player(previous_player)
        else:
            winner = previous_player
        
        return {
            "action": ACTION_WIN,
            "player": winner,
            "points": points,
        }
    
    @staticmethod
    def parse_double_action(text: str, player: str, turn_number: int) -> dict:
        """Parse cube doubling action"""
        match = re.match(r"Doubles\s+=>\s+(\d+)(?:\s*(Takes|Drops|Take|Drop))?", text, re.I)
        if not match:
            return None
        
        cube_value = int(match.group(1))
        response = match.group(2)
        
        result = {
            "turn": turn_number,
            "player": player,
            "action": ACTION_DOUBLE,
            "cube": cube_value,
            "gnu_move": "Double",
        }
        
        if response:
            result["response"] = normalize_action(response)
        
        return result
    
    @staticmethod
    def parse_response_action(text: str, player: str, turn_number: int) -> dict:
        """Parse response to double (Take/Drop)"""
        match = re.match(r"^(Takes|Drops|Take|Drop)$", text.strip(), re.I)
        if not match:
            return None
        
        action = normalize_action(match.group(1))
        gnu_move = "take" if action == ACTION_TAKE else "pass"
        
        return {
            "turn": turn_number,
            "player": player,
            "action": action,
            "gnu_move": gnu_move,
        }
    
    @staticmethod
    def parse_move_action(text: str, player: str, turn_number: int) -> dict:
        """Parse regular move with dice and board actions"""
        if not text:
            return None
        
        text = text.strip()
        
        # FIXED: Handle "XX:" with no moves (empty move)
        # Example: "22:" means dice 2,2 but no moves executed
        if re.match(r"^\d{2}:$", text):
            # Only dice, no moves - this is a pass/skip
            logger.debug(f"Turn {turn_number}: empty move (only dice) for {player}")
            return None
        
        # Check if text starts with valid position or dice
        if not re.match(r"^(\d{1,2}|bar|off|\d\d:)", text, re.I):
            return None
        
        parsed_dice = MoveParser.parse_dice_and_moves(text)
        if not parsed_dice:
            return None
        
        # FIXED: Verify that we have at least some moves
        moves = parsed_dice.get("moves", [])
        if not moves:
            # No moves were parsed - treat as empty move
            logger.debug(f"Turn {turn_number}: no moves parsed for {player}")
            return None
        
        return {
            "turn": turn_number,
            "player": player,
            "action": ACTION_MOVE,
            "dice": parsed_dice.get("dice"),
            "moves": moves,
        }


class TurnContentParser:
    """Parse turn content which may contain Red and Black actions"""
    
    @staticmethod
    def split_turn_sides(turn_content: str) -> tuple:
        """
        Split turn content into black side and red side.
        Returns (black_content, red_content)
        
        FIXED: Uses dice patterns as anchors instead of large spaces
        """
        # Strategy: Use dice patterns as anchors
        dice_matches = find_all_dice_matches(turn_content)
        
        if len(dice_matches) >= 2:
            # Two dice patterns = both players moved
            # Split at the second dice position
            second_dice_start = dice_matches[1].start()
            
            # Everything before second dice = black side
            black_side = turn_content[:second_dice_start].strip()
            # Everything from second dice = red side
            red_side = turn_content[second_dice_start:].strip()
            
            logger.debug(f"Split by dice: black={repr(black_side[:40])}, red={repr(red_side[:40])}")
            return (black_side, red_side)
        
        elif len(dice_matches) == 1:
            # One dice pattern - need to determine which player
            dice_match = dice_matches[0]
            dice_pos = dice_match.start()
            
            # Text before dice
            text_before = turn_content[:dice_pos].strip()
            # Text from dice onward
            text_from_dice = turn_content[dice_pos:].strip()
            
            if text_before:
                # There's text before dice -> entire thing is one side
                # Heuristic: if text_from_dice looks like a complete move
                if re.match(r"\d{2}:\s*(\d+/\d+|bar|off)", text_from_dice):
                    # Looks like a move after black's content
                    logger.debug(f"Split by position: black={repr(turn_content[:40])}")
                    return (turn_content, "")
                else:
                    # Ambiguous - treat as single move
                    logger.debug(f"Split ambiguous: red={repr(turn_content[:40])}")
                    return ("", turn_content)
            else:
                # No text before dice -> only this part
                logger.debug(f"Split no text: red={repr(turn_content[:40])}")
                return ("", turn_content)
        
        else:
            # No dice patterns - entire content is single action (Doubles, Takes, Drops)
            logger.debug(f"Split no dice: action={repr(turn_content[:40])}")
            return (turn_content, "")
    
    @staticmethod
    def parse_side_action(
        side_content: str,
        player: str,
        turn_number: int,
    ) -> dict:
        """Parse a single player's action for the turn"""
        if not side_content:
            return None
        
        side_content = side_content.strip()
        
        # Check for response actions (Take/Drop)
        response = GameActionParser.parse_response_action(
            side_content, player, turn_number
        )
        if response:
            return response
        
        # Check for double action
        double_action = GameActionParser.parse_double_action(
            side_content, player, turn_number
        )
        if double_action:
            return double_action
        
        # Check for move action
        move_action = GameActionParser.parse_move_action(
            side_content, player, turn_number
        )
        if move_action:
            return move_action
        
        return None


class GameMovesCollector:
    """Collect and organize moves from parsed turns"""
    
    def __init__(self):
        self.moves = []
    
    def add_move(self, move_dict: dict) -> None:
        """Add move to collection"""
        if move_dict:
            self.moves.append(move_dict)
    
    def add_skip(self, turn_number: int, player: str) -> None:
        """Add skip action when player doesn't move"""
        self.moves.append({
            "turn": turn_number,
            "player": player,
            "action": ACTION_SKIP,
        })
    
    def get_last_player(self) -> str:
        """Get player who made last non-skip action"""
        for move in reversed(self.moves):
            action = move.get("action")
            if action != ACTION_SKIP:
                return move.get("player")
        return PLAYER_RED


# ============================================================================
# MAIN PARSING FUNCTION
# ============================================================================

def parse_backgammon_moves(content: str) -> list:
    """
    Parse backgammon game moves from .mat file content.
    
    Handles:
    - Win/game end conditions
    - Doubling cube (double/take/drop)
    - Regular moves with dice and board positions
    - Player skips when no move available
    - Empty moves (only dice, no board moves)
    
    Args:
        content: Raw .mat file content string
    
    Returns:
        List of move dictionaries with structure:
        {
            'action': 'move|double|take|drop|skip|win',
            'player': 'red|black',
            'dice': [d1, d2],
            'moves': [{'from': x, 'to': y, 'hit': bool}],
            'turn': int,
        }
    
    Raises:
        ValueError: If game moves cannot be parsed
    """
    try:
        # Step 1: Clean and normalize lines
        cleaned_lines = MatFileParser.clean_lines(content)
        
        # Step 2: Find where game moves start
        start_idx = MatFileParser.find_game_start_index(cleaned_lines)
        
        # Step 3: Initialize collector
        collector = GameMovesCollector()
        
        # Step 4: Parse each turn
        for line in cleaned_lines[start_idx:]:
            line = line.strip()
            if not line:
                continue
            
            # Check for game end/win condition
            win_action = GameActionParser.parse_win_action(
                line,
                collector.get_last_player(),
                collector.moves,
            )
            if win_action:
                collector.add_move(win_action)
                break
            
            # Check if line contains turn number
            turn_match = re.match(TURN_PATTERN, line)
            if not turn_match:
                continue
            
            turn_number = int(turn_match.group(1))
            turn_content = turn_match.group(2)
            
            # Parse the turn content
            _parse_single_turn(
                turn_number,
                turn_content,
                collector,
            )
        
        if not collector.moves:
            logger.warning("No moves parsed from game content")
            return []
        
        logger.info(f"Parsed {len(collector.moves)} moves")
        return collector.moves
    
    except Exception as e:
        logger.error(f"Error parsing backgammon moves: {e}", exc_info=True)
        raise


def _parse_single_turn(
    turn_number: int,
    turn_content: str,
    collector: GameMovesCollector,
) -> None:
    """
    Parse a single turn which may contain actions for both players.
    
    FIXED: Better handling of empty sides and edge cases
    
    Args:
        turn_number: Turn/ply number
        turn_content: Content of turn (may have multiple actions)
        collector: GameMovesCollector to add moves to
    """
    # Split turn into black and red sides
    black_side, red_side = TurnContentParser.split_turn_sides(turn_content)
    
    logger.debug(f"Turn {turn_number}: black_side={repr(black_side[:40])}, red_side={repr(red_side[:40])}")
    
    # Parse black's action (Black plays first in backgammon)
    black_action = None
    if black_side:
        black_action = TurnContentParser.parse_side_action(
            black_side,
            PLAYER_BLACK,
            turn_number,
        )
        
        if black_action:
            collector.add_move(black_action)
            logger.debug(f"Turn {turn_number}: black_action={black_action.get('action')}")
    
    # If black didn't move but has empty side, add skip
    if not black_action and black_side:
        # Black side exists but no valid action = skip
        collector.add_skip(turn_number, PLAYER_BLACK)
        logger.debug(f"Turn {turn_number}: black skip (empty side)")
    elif not black_side and red_side:
        # Black side completely empty = skip
        collector.add_skip(turn_number, PLAYER_BLACK)
        logger.debug(f"Turn {turn_number}: black skip (no side)")
    
    # Parse red's action
    red_action = None
    if red_side:
        red_action = TurnContentParser.parse_side_action(
            red_side,
            PLAYER_RED,
            turn_number,
        )
        
        if red_action:
            collector.add_move(red_action)
            logger.debug(f"Turn {turn_number}: red_action={red_action.get('action')}")
    
    # If red didn't move but has side, add skip
    if not red_action and red_side:
        # Red side exists but no valid action = skip
        collector.add_skip(turn_number, PLAYER_RED)
        logger.debug(f"Turn {turn_number}: red skip (empty side)")
    elif not red_side and black_side:
        # Red side completely empty = skip
        collector.add_skip(turn_number, PLAYER_RED)
        logger.debug(f"Turn {turn_number}: red skip (no side)")
    
    # Handle special case: both players have double actions (shouldn't happen)
    if (
        black_action
        and red_action
        and black_action.get("action") == ACTION_DOUBLE
        and red_action.get("action") == ACTION_DOUBLE
    ):
        logger.warning(f"Turn {turn_number}: both players tried to double")


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def process_mat_file(
    input_file: str,
    output_file: str,
    chat_id: int,
) -> None:
    """Process .mat file and generate annotated output"""
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse games
        games = MatFileParser.parse_games(content)
        if not games:
            raise ValueError("No games found in .mat file")
        
        # Extract match info
        match_info = MatFileParser.extract_game_header(content)
        
        # Create output directory
        output_dir = output_file.rsplit(".", 1)[0] + "_games"
        os.makedirs(output_dir, exist_ok=True)
        
        # Process games
        game_results = _process_games_parallel(
            games,
            output_dir,
            match_info,
        )
        
        # Combine results
        combined_output = {
            "match_info": match_info,
            "chat_id": str(chat_id),
            "total_games": len(games),
            "processed_games": len(game_results),
            "games": game_results,
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(combined_output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Processed {len(game_results)} games to {output_file}")
    
    except Exception as e:
        logger.exception(f"Failed to process {input_file}: {e}")
        raise


def _process_games_parallel(
    games: list,
    output_dir: str,
    match_info: dict,
) -> list:
    """Process multiple games in parallel"""
    results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(games), 4)) as executor:
        futures = {}
        for game in games:
            future = executor.submit(
                _process_single_game,
                game,
                output_dir,
                match_info,
            )
            futures[future] = game["game_number"]
        
        for future in concurrent.futures.as_completed(futures):
            game_number = futures[future]
            try:
                result = future.result()
                results.append(result)
                logger.info(f"Game {game_number} processed successfully")
            except Exception as e:
                logger.error(f"Failed to process game {game_number}: {e}")
    
    return results


def _process_single_game(
    game: dict,
    output_dir: str,
    match_info: dict,
) -> dict:
    """Process single game"""
    # Parse moves
    moves = parse_backgammon_moves(game["content"])
    
    # Track positions
    tracker = BackgammonPositionTracker()
    augmented_moves = tracker.process_game(moves)
    
    # Add player names
    player_info = game.get("player_info")
    if player_info:
        for entry in augmented_moves:
            if entry.get("player") == "red":
                entry["player_name"] = player_info.get("second_player")
            elif entry.get("player") == "black":
                entry["player_name"] = player_info.get("first_player")
    
    # Generate GNUBG tokens and get hints
    gnubg_tokens = GnuBackgammonCommandGenerator.generate_tokens(
        augmented_moves,
        jacobi_rule=match_info.get("jacobi_rule", True),
        match_length=match_info.get("match_length", 0),
    )
    
    augmented_moves = _run_gnubg_and_collect_hints(gnubg_tokens, augmented_moves)
    
    # Save game result
    output_file = os.path.join(output_dir, f"game_{game['game_number']}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "game_number": game["game_number"],
                "player_info": game.get("player_info"),
                "moves": augmented_moves,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    
    return {
        "game_number": game["game_number"],
        "output_file": output_file,
    }


def _run_gnubg_and_collect_hints(tokens: list, moves: list) -> list:
    """Run GNUBG process and collect hints"""
    moves_with_hints = [copy.deepcopy(m) for m in moves]
    for m in moves_with_hints:
        m.setdefault("hints", [])
        m.setdefault("cube_hints", [])
    
    child = None
    try:
        child = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=GNUBG_TIMEOUT)
        time.sleep(GNUBG_STARTUP_DELAY)
        
        # Read startup output
        try:
            child.read_nonblocking(size=4096, timeout=0.2)
        except pexpect.TIMEOUT:
            pass
        
        # Send commands
        for token in tokens:
            cmd = token["cmd"]
            logger.debug(f"GNUBG: {cmd}")
            child.sendline(cmd)
            time.sleep(GNUBG_COMMAND_DELAY)
            
            # Read immediate output
            output = _read_available(child)
            logger.debug(f"GNUBG output: {output[:200]}")
            
            # If hint command, wait for full output
            if token["type"] in ("hint", "cube_hint"):
                target_idx = token.get("target")
                time.sleep(GNUBG_HINT_DELAY)
                
                try:
                    output += child.read_nonblocking(
                        size=HINT_OUTPUT_BUFFER_SIZE,
                        timeout=0.1,
                    )
                except pexpect.TIMEOUT:
                    pass
                
                hints = HintOutputParser.parse(output)
                if hints and target_idx is not None and target_idx < len(moves_with_hints):
                    for hint in hints:
                        if token["type"] == "cube_hint":
                            moves_with_hints[target_idx]["cube_hints"].append(hint)
                        else:
                            moves_with_hints[target_idx]["hints"].append(hint)
        
        return moves_with_hints
    
    finally:
        if child:
            try:
                child.sendline("exit")
                time.sleep(0.1)
                child.sendline("y")
                child.expect(pexpect.EOF, timeout=GNUBG_SHUTDOWN_TIMEOUT)
            except Exception:
                pass
            finally:
                try:
                    if child.isalive():
                        child.close(force=True)
                except Exception:
                    pass


def _read_available(proc, timeout: float = GNUBG_READ_TIMEOUT) -> str:
    """Read available data without blocking"""
    output = ""
    try:
        if proc.stdout:
            rlist, _, _ = select.select([proc.stdout], [], [], timeout)
            if rlist:
                output = proc.stdout.read()
    except Exception as e:
        logger.debug(f"Read error: {e}")
    
    return output


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hint_viewer_refactored_FIXED.py <mat_file> [output_file] [chat_id]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output.json"
    chat_id = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    
    process_mat_file(input_file, output_file, chat_id)