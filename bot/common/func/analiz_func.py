import json
import re
import subprocess
import os
from loguru import logger

import json
import re
import os
import subprocess
from loguru import logger


def analyze_mat_file(mat_file: str) -> str:
    try:
        if not os.path.exists(mat_file):
            logger.error(f".mat-файл не найден: {mat_file}")
            raise FileNotFoundError(f".mat-файл не найден: {mat_file}")

        try:
            subprocess.run(["gnubg", "--version"], check=True, capture_output=True)
        except FileNotFoundError:
            logger.error("GNU Backgammon не установлен или не найден в PATH")
            raise FileNotFoundError("GNU Backgammon не установлен или не найден в PATH")

        gnubg_commands = [
            f"import mat {mat_file}",
            "analyse match",
            "show statistics match",
            "exit",
        ]

        process = subprocess.Popen(
            ["gnubg", "-t"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        stdout, stderr = process.communicate("\n".join(gnubg_commands))
        logger.debug(f"Вывод gnubg:\n{stdout}")
        if process.returncode != 0:
            logger.error(f"Ошибка выполнения gnubg: {stderr}")
            raise RuntimeError(f"Ошибка выполнения gnubg: {stderr}")

        logger.info(f"Анализ матча завершён для файла: {mat_file}")

        # Парсинг в JSON
        stats = {}
        current_section = None
        players = []
        lines = [line.strip() for line in stdout.split("\n") if line.strip()]

        # Извлечение имен игроков
        for line in lines:
            if line.startswith("Player"):
                players = [p.strip() for p in re.split(r"\s{2,}", line) if p.strip()]
                players = players[1:]  # Удаляем "Player"
                break

        for line in lines:
            if any(
                header in line
                for header in [
                    "Chequerplay statistics",
                    "Luck statistics",
                    "Cube statistics",
                    "Overall statistics",
                ]
            ):
                current_section = line.lower().replace(" statistics", "")
                stats[current_section] = {player: {} for player in players}
            elif current_section and not line.startswith("|") and len(line.strip()) > 0:
                parts = [p.strip() for p in re.split(r"\s{2,}", line.strip()) if p.strip()]
                logger.info(parts)
                if len(parts) > 1:
                    key = (
                        parts[0]
                        .lower()
                        .replace(" ", "_")
                        .replace("(", "")
                        .replace(")", "")
                        .replace(".", "")
                    )

                    # Добавляем '_points' к ключам с EMG, если еще не добавлен
                    if "emg" in key and not key.endswith("_points"):
                        key = f"{key}_points"

                    is_rating = "rating" in key

                    if len(parts) - 1 == len(players):
                        # Строки с одним значением на игрока
                        for i, player in enumerate(players):
                            value = parts[i + 1].strip()
                            if is_rating:
                                stats[current_section][player][key] = value
                            else:
                                main_match = re.match(r"([-\+]?[\d\.]+)", value)
                                if main_match:
                                    stats[current_section][player][key] = main_match.group(1)
                                bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
                                if bracket_match:
                                    stats[current_section][player][f"{key}_extra"] = bracket_match.group(1)
                                elif not main_match:
                                    stats[current_section][player][key] = "0"
                    elif len(parts) - 1 == 2 * len(players):
                        # Строки с двумя частями на игрока (main + extra)
                        for i, player in enumerate(players):
                            main_part = parts[1 + 2 * i].strip()
                            extra_part = parts[2 + 2 * i].strip() if 2 + 2 * i < len(parts) else ""
                            value = f"{main_part} {extra_part}".strip()
                            main_match = re.match(r"([-\+]?[\d\.]+)", value)
                            if main_match:
                                stats[current_section][player][key] = main_match.group(1)
                            bracket_match = re.search(r"\(([-+]?[\d\.]+)\)", value)
                            if bracket_match:
                                stats[current_section][player][f"{key}_extra"] = bracket_match.group(1)
                            elif not main_match:
                                stats[current_section][player][key] = "0"
                    else:
                        logger.warning(f"Неизвестный формат строки: {line}")

        # Проверяем и исправляем значения Snowie error rate
        for player in players:
            if "overall" in stats and "snowie_error_rate" not in stats["overall"][player]:
                stats["overall"][player]["snowie_error_rate"] = "0"

        return json.dumps(stats, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Ошибка при анализе матча: {e}")
        raise

if __name__ == "__main__":
    mat_file = r"ppnards-match-a552d706-7879-4832-94ff-8e1d570bac8f-protocol.mat"
    try:
        result = analyze_mat_file(mat_file)
        print("Анализ:\n", result)
    except Exception as e:
        print("Ошибка:", e)
