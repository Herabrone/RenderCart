import base64
import hashlib
import os
import secrets
from datetime import UTC, datetime

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from rendercart.auth.models import RecoveryCode, User
from rendercart.core.config import get_settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def digest_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def encrypt_secret(value: str) -> str:
    return base64.urlsafe_b64encode(encrypt_bytes(value.encode("utf-8"))).decode("ascii")


def decrypt_secret(value: str) -> str:
    payload = base64.urlsafe_b64decode(value.encode("ascii"))
    return decrypt_bytes(payload).decode("utf-8")


def _encryption_key() -> bytes:
    return hashlib.sha256(get_settings().encryption_key.get_secret_value().encode()).digest()


def encrypt_bytes(value: bytes) -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(_encryption_key()).encrypt(nonce, value, None)


def decrypt_bytes(value: bytes) -> bytes:
    if len(value) < 28:
        raise ValueError("encrypted payload is malformed")
    return AESGCM(_encryption_key()).decrypt(value[:12], value[12:], None)


def create_totp_secret(user: User) -> tuple[str, str]:
    secret = pyotp.random_base32()
    user.totp_secret_enc = encrypt_secret(secret)
    provisioning_uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name="RenderCart",
    )
    return secret, provisioning_uri


def verify_totp_or_recovery(db: Session, user: User, code: str) -> bool:
    if user.totp_secret_enc:
        secret = decrypt_secret(user.totp_secret_enc)
        if pyotp.TOTP(secret).verify(code, valid_window=1):
            return True
    recovery = db.scalar(select(RecoveryCode).where(RecoveryCode.token_hash == digest_secret(code)))
    if recovery is None or recovery.user_id != user.id or recovery.used_at is not None:
        return False
    recovery.used_at = datetime.now(UTC)
    return True
