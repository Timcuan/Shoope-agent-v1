import hashlib
import hmac
import time


def generate_timestamp() -> int:
    return int(time.time())


def generate_signature(
    partner_key: str,
    partner_id: str,
    api_path: str,
    timestamp: int,
    access_token: str = "",
    shop_id: str = "",
) -> str:
    base_string = f"{partner_id}{api_path}{timestamp}{access_token}{shop_id}"
    sign = hmac.new(
        partner_key.encode("utf-8"),
        base_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return sign


def generate_auth_url(
    base_url: str,
    partner_id: str,
    partner_key: str,
    redirect_url: str,
) -> str:
    path = "/api/v2/shop/auth_partner"
    timestamp = generate_timestamp()
    sign = generate_signature(partner_key, partner_id, path, timestamp)
    return f"{base_url}{path}?partner_id={partner_id}&timestamp={timestamp}&sign={sign}&redirect={redirect_url}"
