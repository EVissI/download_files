import hmac
import hashlib
import urllib.parse
import json
from bot.config import settings

def verify_telegram_webapp_data(init_data: str) -> dict | None:
    """
    Verifies the data received from the Telegram Web App.
    Returns the user data if valid, otherwise None.
    """
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if 'hash' not in parsed_data:
            return None
        
        received_hash = parsed_data.pop('hash')
        data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(parsed_data.items())])
        
        secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if computed_hash == received_hash:
            return {k: json.loads(v) if k == 'user' else v for k, v in parsed_data.items()}
        return None
    except Exception:
        return None
