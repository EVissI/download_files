"""Хеш пароля для входа и AES-GCM копия для просмотра в FAB."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger
from werkzeug.security import check_password_hash, generate_password_hash

_AAD = b"web_user.password"
_NONCE_LEN = 12


def hash_password(raw: str) -> str:
    return generate_password_hash(
        (raw or "").strip(),
        method="pbkdf2:sha256",
        salt_length=16,
    )


def verify_password(password_hash: str, raw: str) -> bool:
    if not password_hash or raw is None:
        return False
    cleaned = raw.strip()
    if not cleaned:
        return False
    try:
        return bool(check_password_hash(password_hash, cleaned))
    except Exception:
        logger.warning("WebUser password hash check failed")
        return False


def passwords_match(
    password_hash: str, encrypted: str | None, raw: str
) -> bool:
    cleaned = (raw or "").strip()
    if not cleaned:
        return False
    if verify_password(password_hash, cleaned):
        return True
    plain = decrypt_password(encrypted)
    if plain is None:
        return False
    try:
        return secrets.compare_digest(plain, cleaned)
    except (TypeError, ValueError):
        return False


def _aes_key() -> bytes:
    from bot.config import settings

    secret = (settings.WEB_USER_PASSWORD_KEY or settings.SECRET_KEY or "").encode(
        "utf-8"
    )
    return hashlib.sha256(secret).digest()


def encrypt_password(raw: str) -> str:
    plain = (raw or "").strip().encode("utf-8")
    nonce = os.urandom(_NONCE_LEN)
    token = AESGCM(_aes_key()).encrypt(nonce, plain, _AAD)
    return base64.urlsafe_b64encode(nonce + token).decode("ascii")


def decrypt_password(blob: str | None) -> str | None:
    if not blob:
        return None
    try:
        data = base64.urlsafe_b64decode(blob.encode("ascii"))
        nonce, token = data[:_NONCE_LEN], data[_NONCE_LEN:]
        if len(nonce) != _NONCE_LEN or not token:
            return None
        plain = AESGCM(_aes_key()).decrypt(nonce, token, _AAD)
        return plain.decode("utf-8")
    except Exception:
        return None


def store_password(raw: str) -> tuple[str, str]:
    cleaned = (raw or "").strip()
    return hash_password(cleaned), encrypt_password(cleaned)
