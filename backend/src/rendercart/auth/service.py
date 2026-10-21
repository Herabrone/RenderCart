from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from rendercart.auth.models import AuthSession, AuthToken, OAuthAccount, TokenPurpose, User
from rendercart.auth.security import digest_secret, hash_password, new_secret, verify_password
from rendercart.core.access import StaffRole
from rendercart.core.config import get_settings


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def find_or_create_oauth_user(
    db: Session,
    provider: str,
    provider_user_id: str,
    verified_email: str,
    display_name: str | None,
) -> User:
    account = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        )
    )
    if account:
        user = db.get(User, account.user_id)
        if user is None or user.is_banned:
            raise AuthError("Account is unavailable", 403)
        return user

    email = normalize_email(verified_email)
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            email_verified_at=datetime.now(UTC),
            display_name=display_name,
            staff_role=StaffRole.USER,
        )
        db.add(user)
        db.flush()
    elif user.is_banned:
        raise AuthError("Account is unavailable", 403)
    db.add(
        OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
        )
    )
    return user


def create_user(
    db: Session,
    email: str,
    password: str,
    display_name: str | None = None,
) -> tuple[User, str]:
    normalized = normalize_email(email)
    if db.scalar(select(User).where(User.email == normalized)):
        raise AuthError("An account with this email already exists", 409)
    user = User(
        email=normalized,
        password_hash=hash_password(password),
        display_name=display_name.strip() if display_name else None,
        staff_role=StaffRole.USER,
    )
    db.add(user)
    db.flush()
    token = create_auth_token(db, user, TokenPurpose.VERIFY_EMAIL)
    return user, token


def create_auth_token(db: Session, user: User, purpose: TokenPurpose) -> str:
    settings = get_settings()
    token = new_secret()
    db.add(
        AuthToken(
            token_hash=digest_secret(token),
            user_id=user.id,
            purpose=purpose,
            expires_at=datetime.now(UTC) + timedelta(minutes=settings.auth_token_ttl_minutes),
        )
    )
    return token


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if (
        user is None
        or user.password_hash is None
        or not verify_password(user.password_hash, password)
    ):
        raise AuthError("Invalid email or password", 401)
    if user.is_banned:
        raise AuthError("Account is unavailable", 403)
    return user


def create_session(
    db: Session,
    user: User,
    ip: str | None,
    user_agent: str | None,
    mfa_verified: bool = True,
) -> tuple[str, AuthSession]:
    settings = get_settings()
    token = new_secret()
    now = datetime.now(UTC)
    hours = settings.admin_session_ttl_hours if user.staff_role != StaffRole.USER else None
    expires_at = now + (
        timedelta(hours=hours) if hours else timedelta(days=settings.session_ttl_days)
    )
    session = AuthSession(
        token_hash=digest_secret(token),
        user_id=user.id,
        expires_at=expires_at,
        ip=ip,
        user_agent=user_agent,
        mfa_verified=mfa_verified,
    )
    db.add(session)
    return token, session


def get_session_user(db: Session, raw_token: str | None) -> tuple[User, AuthSession] | None:
    if not raw_token:
        return None
    session = db.get(AuthSession, digest_secret(raw_token))
    if session is None:
        return None
    now = datetime.now(UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        db.delete(session)
        return None
    user = db.get(User, session.user_id)
    if user is None or user.is_banned:
        return None
    session.last_seen_at = now
    return user, session


def verify_email(db: Session, raw_token: str) -> User:
    user = consume_token(db, raw_token, TokenPurpose.VERIFY_EMAIL)
    user.email_verified_at = datetime.now(UTC)
    return user


def consume_token(
    db: Session,
    raw_token: str,
    purpose: TokenPurpose,
) -> User:
    token = db.get(AuthToken, digest_secret(raw_token))
    now = datetime.now(UTC)
    if token is None or token.purpose != purpose or token.used_at is not None:
        raise AuthError("This link is invalid or has already been used", 400)
    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        raise AuthError("This link has expired", 400)
    user = db.get(User, token.user_id)
    if user is None:
        raise AuthError("This link is invalid", 400)
    token.used_at = now
    return user


def reset_password(db: Session, raw_token: str, new_password: str) -> None:
    user = consume_token(db, raw_token, TokenPurpose.RESET_PASSWORD)
    user.password_hash = hash_password(new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
