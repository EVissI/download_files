import hmac
import hashlib
import urllib.parse
import json
from bot.config import settings

from loguru import logger

def verify_telegram_webapp_data(init_data: str) -> dict | None:
    """
    Verifies the data received from the Telegram Web App.
    Returns the user data if valid, otherwise None.
    """
    try:
        logger.debug(f"Verifying Telegram WebApp data: {init_data[:50]}...")
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if 'hash' not in parsed_data:
            logger.warning("No hash in parsed_data")
            return None
        
        received_hash = parsed_data.pop('hash')
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(parsed_data.items())])
        
        secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if computed_hash == received_hash:
            user_info = {k: json.loads(v) if k == 'user' else v for k, v in parsed_data.items()}
            logger.info(f"Telegram WebApp data verified successfully for user {user_info.get('user', {}).get('id')}")
            return user_info
        
        logger.warning(f"Hash mismatch: received={received_hash}, computed={computed_hash}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Telegram WebApp data: {e}")
        return None
