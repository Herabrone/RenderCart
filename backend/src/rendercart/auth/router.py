import hashlib
import secrets
from datetime import UTC, datetime
from typing import Annotated

import httpx2
import structlog
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.httpx_client import OAuth2Client
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rendercart.auth import service
from rendercart.auth.email import send_auth_link
from rendercart.auth.models import AuthSession, RecoveryCode, TokenPurpose, User
from rendercart.auth.schemas import (
    EmailRequest,
    LoginRequest,
    MagicSignInRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenRequest,
    TotpConfirmRequest,
    UserResponse,
)
from rendercart.auth.security import (
    create_totp_secret,
    digest_secret,
    new_secret,
    verify_totp_or_recovery,
)
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.core.ownership import attach_guest_data
from rendercart.core.redis import increment_window
from rendercart.core.turnstile import verify_turnstile

router = APIRouter(prefix="/api/auth", tags=["auth"])
Db = Annotated[Session, Depends(get_db)]
logger = structlog.get_logger(__name__)


def _user_response(user: User, mfa_verified: bool = True) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        email_verified=user.email_verified_at is not None,
        display_name=user.display_name,
        staff_role=user.staff_role.value,
        totp_enabled=user.totp_enabled,
        mfa_verified=mfa_verified,
    )


def _secure_cookie() -> bool:
    return get_settings().app_env == "production"


def _set_session(
    response: Response,
    request: Request,
    db: Session,
    user: User,
    mfa_verified: bool = True,
) -> None:
    attach_guest_data(db, user, request.cookies.get(get_settings().guest_cookie_name))
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", "")[:512] or None
    raw_session, session = service.create_session(db, user, ip, user_agent, mfa_verified)
    db.commit()
    settings = get_settings()
    max_age = max(0, int((session.expires_at - datetime.now(UTC)).total_seconds()))
    response.set_cookie(
        settings.session_cookie_name,
        raw_session,
        max_age=max_age,
        secure=_secure_cookie(),
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        secrets.token_urlsafe(32),
        max_age=max_age,
        secure=_secure_cookie(),
        httponly=False,
        samesite="lax",
        path="/",
    )


def enforce_auth_limits(request: Request, action: str, email: str | None = None) -> None:
    """Enforce per-IP and per-address auth limits using an atomic Redis window."""
    ip = request.client.host if request.client else "unknown"
    limits = [(f"auth:{action}:ip:{ip}", 10, 900)]
    if email:
        email_hash = hashlib.sha256(service.normalize_email(email).encode()).hexdigest()
        limits.append((f"auth:{action}:email:{email_hash}", 5, 900))
    try:
        for key, maximum, ttl in limits:
            if increment_window(key, ttl) > maximum:
                raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    except HTTPException:
        raise
    except RedisError as exc:
        logger.exception("auth_rate_limit_backend_unavailable")
        raise HTTPException(
            status_code=503, detail="Authentication is temporarily unavailable"
        ) from exc


def require_csrf(
    csrf_header: Annotated[str | None, Header(alias="X-RC-CSRF")] = None,
    csrf_cookie: Annotated[str | None, Cookie(alias="rc_csrf")] = None,
) -> None:
    if not csrf_header or not csrf_cookie or not secrets.compare_digest(csrf_header, csrf_cookie):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


@router.get("/csrf")
def issue_csrf(response: Response) -> dict[str, str]:
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        get_settings().csrf_cookie_name,
        token,
        secure=_secure_cookie(),
        httponly=False,
        samesite="lax",
        path="/",
    )
    return {"csrf_token": token}


@router.get("/oauth/{provider}/start")
def start_oauth(provider: str, response: Response) -> Response:
    settings = get_settings()
    if provider == "google":
        client_id = settings.google_client_id
        endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
        scope = "openid email profile"
    elif provider == "github":
        client_id = settings.github_client_id
        endpoint = "https://github.com/login/oauth/authorize"
        scope = "read:user user:email"
    else:
        raise HTTPException(status_code=404, detail="OAuth provider not found")
    if not client_id:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured")

    verifier = secrets.token_urlsafe(48)
    callback = f"{settings.app_base_url.rstrip('/')}/api/auth/oauth/{provider}/callback"
    oauth_client = OAuth2Client(
        client_id,
        scope=scope,
        redirect_uri=callback,
        code_challenge_method="S256",
    )
    authorization_url, state = oauth_client.create_authorization_url(
        endpoint,
        code_verifier=verifier,
    )
    oauth_client.close()
    serializer = URLSafeTimedSerializer(
        settings.secret_key.get_secret_value(), salt=f"oauth-{provider}"
    )
    signed_state = serializer.dumps({"state": state, "verifier": verifier})
    redirect = RedirectResponse(authorization_url, status_code=302)
    redirect.set_cookie(
        f"rc_oauth_{provider}",
        signed_state,
        max_age=600,
        secure=_secure_cookie(),
        httponly=True,
        samesite="lax",
        path=f"/api/auth/oauth/{provider}/callback",
    )
    return redirect


def _exchange_oauth_code(
    provider: str,
    code: str,
    verifier: str,
    state: str,
    callback: str,
) -> tuple[str, str, str | None]:
    settings = get_settings()
    if provider == "google":
        client_id = settings.google_client_id
        client_secret = (
            settings.google_client_secret.get_secret_value()
            if settings.google_client_secret
            else None
        )
        token_url = "https://oauth2.googleapis.com/token"
    elif provider == "github":
        client_id = settings.github_client_id
        client_secret = (
            settings.github_client_secret.get_secret_value()
            if settings.github_client_secret
            else None
        )
        token_url = "https://github.com/login/oauth/access_token"
    else:
        raise HTTPException(status_code=404, detail="OAuth provider not found")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail=f"{provider.title()} sign-in is not configured")

    with OAuth2Client(
        client_id,
        client_secret,
        scope="openid email profile" if provider == "google" else "read:user user:email",
        redirect_uri=callback,
        token_endpoint_auth_method="client_secret_post",
        timeout=10.0,
        follow_redirects=False,
    ) as client:
        token = client.fetch_token(
            token_url,
            code=code,
            redirect_uri=callback,
            code_verifier=verifier,
            state=state,
        )
        access_token = token.get("access_token")
        if not isinstance(access_token, str):
            raise HTTPException(status_code=401, detail="OAuth sign-in failed")
        if provider == "google":
            profile = client.get("https://openidconnect.googleapis.com/v1/userinfo")
            profile.raise_for_status()
            data = profile.json()
            subject, email = data.get("sub"), data.get("email")
            verified = data.get("email_verified") is True
            display_name = data.get("name")
        else:
            profile = client.get("https://api.github.com/user")
            profile.raise_for_status()
            account = profile.json()
            subject = str(account.get("id")) if account.get("id") is not None else None
            display_name = account.get("name") or account.get("login")
            emails = client.get("https://api.github.com/user/emails")
            emails.raise_for_status()
            email_records = emails.json()
            verified_record = next(
                (
                    item
                    for item in email_records
                    if item.get("primary") is True and item.get("verified") is True
                ),
                None,
            )
            email = verified_record.get("email") if verified_record else None
            verified = bool(email)
    if not isinstance(subject, str) or not isinstance(email, str) or not verified:
        raise HTTPException(status_code=400, detail="A verified provider email is required")
    return subject, email, display_name if isinstance(display_name, str) else None


@router.get("/oauth/{provider}/callback")
def finish_oauth(
    provider: str,
    request: Request,
    code: str,
    state: str,
    db: Db,
) -> Response:
    if provider not in {"google", "github"}:
        raise HTTPException(status_code=404, detail="OAuth provider not found")
    settings = get_settings()
    signed_state = request.cookies.get(f"rc_oauth_{provider}")
    serializer = URLSafeTimedSerializer(
        settings.secret_key.get_secret_value(), salt=f"oauth-{provider}"
    )
    try:
        state_payload = serializer.loads(signed_state or "", max_age=600)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=400, detail="OAuth state expired or invalid") from exc
    if not isinstance(state_payload, dict) or state_payload.get("state") != state:
        raise HTTPException(status_code=400, detail="OAuth state validation failed")

    callback = f"{settings.app_base_url.rstrip('/')}/api/auth/oauth/{provider}/callback"
    try:
        provider_user_id, email, display_name = _exchange_oauth_code(
            provider,
            code,
            str(state_payload["verifier"]),
            str(state_payload["state"]),
            callback,
        )
    except httpx2.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail="OAuth provider could not complete sign-in"
        ) from exc
    except OAuthError as exc:
        raise HTTPException(status_code=401, detail="OAuth provider rejected sign-in") from exc
    user = service.find_or_create_oauth_user(
        db,
        provider,
        provider_user_id,
        email,
        display_name,
    )
    attach_guest_data(db, user, request.cookies.get(settings.guest_cookie_name))
    raw_session, session = service.create_session(
        db,
        user,
        request.client.host if request.client else None,
        request.headers.get("user-agent", "")[:512] or None,
        user.staff_role.value == "user" and not user.totp_enabled,
    )
    db.commit()
    response = RedirectResponse(f"{settings.app_base_url.rstrip('/')}/account", status_code=302)
    response.set_cookie(
        settings.session_cookie_name,
        raw_session,
        max_age=max(0, int((session.expires_at - datetime.now(UTC)).total_seconds())),
        secure=_secure_cookie(),
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        secrets.token_urlsafe(32),
        max_age=max(0, int((session.expires_at - datetime.now(UTC)).total_seconds())),
        secure=_secure_cookie(),
        httponly=False,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(f"rc_oauth_{provider}", path=f"/api/auth/oauth/{provider}/callback")
    return response


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
def signup(payload: SignupRequest, request: Request, db: Db) -> UserResponse:
    enforce_auth_limits(request, "signup", str(payload.email))
    ip = request.client.host if request.client else "unknown"
    if not verify_turnstile(payload.turnstile_token, ip):
        raise HTTPException(status_code=403, detail="Complete the anti-bot check before signing up")
    try:
        user, raw_token = service.create_user(
            db,
            str(payload.email),
            payload.password,
            payload.display_name,
        )
        attach_guest_data(db, user, request.cookies.get(get_settings().guest_cookie_name))
        db.commit()
    except service.AuthError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="An account with this email already exists"
        ) from exc
    try:
        send_auth_link(user.email, raw_token, "verify_email")
    except (OSError, TimeoutError):
        # Signup succeeds; the verification email can be resent after email delivery is configured.
        pass
    return _user_response(user)


@router.post("/login", response_model=UserResponse, dependencies=[Depends(require_csrf)])
def login(payload: LoginRequest, request: Request, response: Response, db: Db) -> UserResponse:
    enforce_auth_limits(request, "login", str(payload.email))
    try:
        user = service.authenticate(db, str(payload.email), payload.password)
    except service.AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if user.totp_enabled:
        if not payload.totp_code or not verify_totp_or_recovery(db, user, payload.totp_code):
            raise HTTPException(
                status_code=401,
                detail="A valid authenticator or recovery code is required",
            )
    mfa_verified = user.staff_role.value == "user" or user.totp_enabled
    _set_session(response, request, db, user, mfa_verified)
    return _user_response(user, mfa_verified)


@router.post("/magic-link", dependencies=[Depends(require_csrf)])
def request_magic_link(payload: EmailRequest, request: Request, db: Db) -> dict[str, str]:
    enforce_auth_limits(request, "magic-link", str(payload.email))
    user = db.scalar(select(User).where(User.email == service.normalize_email(str(payload.email))))
    if user is not None and not user.is_banned:
        raw_token = service.create_auth_token(db, user, TokenPurpose.MAGIC_LINK)
        db.commit()
        try:
            send_auth_link(user.email, raw_token, "magic_link")
        except (OSError, TimeoutError):
            pass
    return {"status": "If the account exists, a sign-in link has been sent"}


@router.post("/verify-email/request", dependencies=[Depends(require_csrf)])
def request_email_verification(
    payload: EmailRequest,
    request: Request,
    db: Db,
) -> dict[str, str]:
    enforce_auth_limits(request, "verify-email-request", str(payload.email))
    user = db.scalar(select(User).where(User.email == service.normalize_email(str(payload.email))))
    if user is not None and user.email_verified_at is None and not user.is_banned:
        raw_token = service.create_auth_token(db, user, TokenPurpose.VERIFY_EMAIL)
        db.commit()
        try:
            send_auth_link(user.email, raw_token, "verify_email")
        except (OSError, TimeoutError):
            pass
    return {"status": "If the account needs verification, a link has been sent"}


@router.post("/magic", response_model=UserResponse, dependencies=[Depends(require_csrf)])
def sign_in_with_magic_link(
    payload: MagicSignInRequest,
    request: Request,
    response: Response,
    db: Db,
) -> UserResponse:
    enforce_auth_limits(request, "magic-signin")
    try:
        user = service.consume_token(db, payload.token, TokenPurpose.MAGIC_LINK)
        if user.is_banned:
            raise service.AuthError("Account is unavailable", 403)
        # A one-time sign-in link proves control of the mailbox. This also
        # completes guest day-pass claims, whose account is created only after
        # Stripe confirms payment.
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        if user.totp_enabled and (
            not payload.totp_code or not verify_totp_or_recovery(db, user, payload.totp_code)
        ):
            raise service.AuthError("A valid authenticator or recovery code is required", 401)
        mfa_verified = user.staff_role.value == "user" or user.totp_enabled
        _set_session(response, request, db, user, mfa_verified)
    except service.AuthError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _user_response(user, mfa_verified)


@router.post("/password-reset/request", dependencies=[Depends(require_csrf)])
def request_password_reset(payload: EmailRequest, request: Request, db: Db) -> dict[str, str]:
    enforce_auth_limits(request, "password-reset", str(payload.email))
    user = db.scalar(select(User).where(User.email == service.normalize_email(str(payload.email))))
    if user is not None and user.password_hash and not user.is_banned:
        raw_token = service.create_auth_token(db, user, TokenPurpose.RESET_PASSWORD)
        db.commit()
        try:
            send_auth_link(user.email, raw_token, "reset_password")
        except (OSError, TimeoutError):
            pass
    return {"status": "If the account exists, a password reset link has been sent"}


@router.post("/password-reset", status_code=204, dependencies=[Depends(require_csrf)])
def reset_password(payload: ResetPasswordRequest, request: Request, db: Db) -> Response:
    enforce_auth_limits(request, "password-reset-complete")
    try:
        service.reset_password(db, payload.token, payload.new_password)
        db.commit()
    except service.AuthError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
def current_user(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> UserResponse:
    result = service.get_session_user(db, raw_session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user, session = result
    db.commit()
    return _user_response(user, session.mfa_verified)


def _require_session(db: Session, raw_session: str | None) -> tuple[User, AuthSession]:
    result = service.get_session_user(db, raw_session)
    if result is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return result


def require_staff_mfa(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> User:
    user, session = _require_session(db, raw_session)
    if user.staff_role.value != "user" and (not user.totp_enabled or not session.mfa_verified):
        raise HTTPException(status_code=403, detail="Staff access requires verified TOTP")
    return user


@router.post("/totp/verify", dependencies=[Depends(require_csrf)])
def verify_totp_for_session(
    payload: TotpConfirmRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, str]:
    user, session = _require_session(db, raw_session)
    if not user.totp_enabled or not verify_totp_or_recovery(db, user, payload.code):
        raise HTTPException(status_code=400, detail="Invalid authenticator or recovery code")
    session.mfa_verified = True
    db.commit()
    return {"status": "verified"}


@router.post("/totp/setup", dependencies=[Depends(require_csrf)])
def setup_totp(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, str]:
    user, _ = _require_session(db, raw_session)
    if user.totp_enabled:
        raise HTTPException(status_code=409, detail="Two-factor authentication is already enabled")
    secret, provisioning_uri = create_totp_secret(user)
    db.commit()
    return {"secret": secret, "provisioning_uri": provisioning_uri}


@router.post("/totp/confirm", dependencies=[Depends(require_csrf)])
def confirm_totp(
    payload: TotpConfirmRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, list[str]]:
    user, session = _require_session(db, raw_session)
    if user.totp_enabled or not user.totp_secret_enc:
        raise HTTPException(status_code=409, detail="Start two-factor setup before confirming")
    if not verify_totp_or_recovery(db, user, payload.code):
        raise HTTPException(status_code=400, detail="Invalid authenticator code")
    user.totp_enabled = True
    session.mfa_verified = True
    recovery_codes = [new_secret()[:16] for _ in range(10)]
    for recovery_code in recovery_codes:
        db.add(RecoveryCode(token_hash=digest_secret(recovery_code), user_id=user.id))
    db.commit()
    return {"recovery_codes": recovery_codes}


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(
    response: Response,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    if raw_session:
        from rendercart.auth.models import AuthSession
        from rendercart.auth.security import digest_secret

        session = db.get(AuthSession, digest_secret(raw_session))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    response.delete_cookie(get_settings().csrf_cookie_name, path="/")
    response.status_code = 204
    return response


@router.post(
    "/verify-email",
    response_model=UserResponse,
    dependencies=[Depends(require_csrf)],
)
def verify_email(payload: TokenRequest, request: Request, db: Db) -> UserResponse:
    enforce_auth_limits(request, "verify-email")
    try:
        user = service.verify_email(db, payload.token)
        db.commit()
    except service.AuthError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _user_response(user)
