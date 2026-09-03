import hmac
import hashlib
import time
import urllib.parse
import json
from bot.config import settings

from loguru import logger

_MAX_INIT_DATA_AGE_SEC = 24 * 3600


def verify_telegram_webapp_data(init_data: str) -> dict | None:
    """
    Verifies the data received from the Telegram Web App.
    Returns the user data if valid, otherwise None.
    """
    try:
        logger.debug(f"Verifying Telegram WebApp data: {init_data[:50]}...")
        parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if 'hash' not in parsed_data:
            logger.warning("No hash in parsed_data")
            return None
        
        received_hash = parsed_data.pop('hash')
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(parsed_data.items())])
        
        secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("Telegram WebApp hash mismatch")
            return None

        try:
            auth_date = int(parsed_data.get("auth_date") or 0)
        except (TypeError, ValueError):
            auth_date = 0
        if auth_date <= 0 or abs(time.time() - auth_date) > _MAX_INIT_DATA_AGE_SEC:
            logger.warning("Telegram WebApp auth_date expired or missing")
            return None

        user_info = {k: json.loads(v) if k == 'user' else v for k, v in parsed_data.items()}
        logger.info(f"Telegram WebApp data verified successfully for user {user_info.get('user', {}).get('id')}")
        return user_info
    except Exception as e:
        logger.error(f"Error verifying Telegram WebApp data: {e}")
        return None
