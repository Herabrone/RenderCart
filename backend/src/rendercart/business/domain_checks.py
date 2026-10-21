from datetime import UTC, datetime
from urllib.parse import quote

from rendercart.safety.fetch import safe_get


def rdap_domain_expiry(domain: str) -> datetime:
    """Return the registration expiry event from the RDAP bootstrap service."""
    response = safe_get(
        f"https://rdap.org/domain/{quote(domain, safe='.-')}",
        timeout_seconds=10,
        max_bytes=512_000,
        max_redirects=5,
    )
    if response.status != 200:
        raise ValueError("rdap_lookup_failed")
    import json

    try:
        payload = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("rdap_response_invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("rdap_response_invalid")
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("rdap_expiry_missing")
    for event in events:
        if not isinstance(event, dict):
            continue
        action = event.get("eventAction")
        event_date = event.get("eventDate")
        if not isinstance(action, str) or "expir" not in action.casefold():
            continue
        if not isinstance(event_date, str):
            continue
        try:
            parsed = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    raise ValueError("rdap_expiry_missing")
