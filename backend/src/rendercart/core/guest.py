from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from rendercart.core.config import get_settings


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        get_settings().secret_key.get_secret_value(), salt="rendercart-guest"
    )


def new_guest_id() -> str:
    import uuid

    return uuid.uuid4().hex


def encode_guest_id(guest_id: str) -> str:
    return _serializer().dumps(guest_id)


def decode_guest_id(raw_guest: str | None, max_age: int = 30 * 86400) -> str | None:
    if not raw_guest:
        return None
    try:
        value = _serializer().loads(raw_guest, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    return value if isinstance(value, str) else None
