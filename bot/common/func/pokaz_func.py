import pexpect
import time
from loguru import logger
from .hint_viewer import read_hint_output, parse_hint_output


def get_hints_for_xgid(xgid: str) -> list:
    """
    Получает подсказки для заданной позиции XGID с помощью gnubg.

    Args:
        xgid (str): Строка XGID позиции.

    Returns:
        list: Список спарсенных подсказок.
    """
    child = pexpect.spawn("gnubg -t", encoding="utf-8", timeout=2)
    try:
        time.sleep(0.2)
        try:
            child.read_nonblocking(size=4096, timeout=0.2)
        except Exception:
            pass

        child.sendline(f"set gnubgid {xgid}")
        time.sleep(0.1)
        child.sendline("hint")
        time.sleep(0.1)

        hint_output = read_hint_output(child, "hint")
        hints = parse_hint_output(hint_output)

        return hints

    except Exception as e:
        logger.error(f"Ошибка при получении hints для XGID {xgid}: {e}", exc_info=True)
        return []

    finally:
        try:
            if child.isalive():
                child.close(force=True)
        except Exception:
            pass

