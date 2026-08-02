"""
Версия статических ассетов для cache-busting в URL (?t=…).

Приоритет:
1. STATIC_ASSET_VERSION из окружения / .env (удобно на деплое)
2. max mtime файлов в bot/static (считается один раз при старте процесса)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _static_dir() -> Path:
    # bot/common/utils/static_assets.py → repo root / bot / static
    return Path(__file__).resolve().parents[2] / "static"


def _max_mtime_version(root: Path) -> str:
    newest = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                try:
                    mtime = int(os.path.getmtime(os.path.join(dirpath, name)))
                except OSError:
                    continue
                if mtime > newest:
                    newest = mtime
    except OSError:
        pass
    return str(newest or 1)


@lru_cache(maxsize=1)
def get_static_asset_version() -> str:
    """
    Стабильная в рамках жизни процесса строка для ?t= в ссылках на /static.
    После деплоя/рестарта или смены STATIC_ASSET_VERSION клиенты получат новый URL.
    """
    env_val = (os.environ.get("STATIC_ASSET_VERSION") or "").strip()
    if not env_val:
        try:
            from bot.config import settings

            env_val = str(getattr(settings, "STATIC_ASSET_VERSION", "") or "").strip()
        except Exception:
            env_val = ""
    if env_val:
        return env_val[:64]
    return _max_mtime_version(_static_dir())
