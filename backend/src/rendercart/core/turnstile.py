import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from rendercart.core.config import get_settings


def verify_turnstile(token: str | None, ip: str) -> bool:
    settings = get_settings()
    secret = settings.turnstile_secret_key
    if not secret:
        return settings.app_env != "production"
    if not token:
        return False
    request = Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=urlencode(
            {"secret": secret.get_secret_value(), "response": token, "remoteip": ip}
        ).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read())
        return isinstance(result, dict) and result.get("success") is True
    except Exception:
        return False
