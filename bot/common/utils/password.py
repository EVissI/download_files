"""Хеширование паролей веб-пользователей (Werkzeug)."""

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(raw: str) -> str:
    return generate_password_hash((raw or "").strip())


def verify_password(password_hash: str, raw: str) -> bool:
    if not password_hash or raw is None:
        return False
    try:
        return check_password_hash(password_hash, raw)
    except (ValueError, TypeError):
        return False
