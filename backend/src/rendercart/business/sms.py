"""Minimal Twilio Programmable Messaging client for fixed-host SMS delivery."""

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from rendercart.core.config import get_settings


class SmsDeliveryError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def send_twilio_sms(to: str, body: str) -> None:
    """Submit one SMS to Twilio; returns only after Twilio accepts the Message resource."""
    settings = get_settings()
    account_sid = settings.twilio_account_sid or ""
    token = settings.twilio_auth_token.get_secret_value() if settings.twilio_auth_token else ""
    sender = settings.twilio_from_number or ""
    if not re.fullmatch(r"AC[0-9a-fA-F]{32}", account_sid):
        raise SmsDeliveryError("SMS provider is not configured")
    if not token or not re.fullmatch(r"\+[1-9][0-9]{7,14}", sender):
        raise SmsDeliveryError("SMS provider is not configured")
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", to):
        raise SmsDeliveryError("Invalid SMS destination")

    credentials = base64.b64encode(f"{account_sid}:{token}".encode()).decode("ascii")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    request = Request(
        url,
        data=urlencode({"To": to, "From": sender, "Body": body[:1400]}).encode(),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=8) as response:
            payload = json.loads(response.read(32_768))
            if not 200 <= response.status < 300 or not payload.get("sid"):
                raise SmsDeliveryError("SMS provider did not accept the message")
    except HTTPError as exc:
        raise SmsDeliveryError(f"SMS provider rejected the message ({exc.code})") from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise SmsDeliveryError("SMS provider request failed") from exc
