from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pyotp
import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from rendercart.auth import router as auth_router
from rendercart.auth.models import User
from rendercart.core.config import get_settings
from rendercart.core.guest import encode_guest_id
from rendercart.jobs.models import Job, JobState, Upload

enforce_auth_limits = auth_router.enforce_auth_limits


@pytest.fixture
def sent_links(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    links: list[tuple[str, str, str]] = []

    def capture(email: str, token: str, purpose: str) -> None:
        links.append((email, token, purpose))

    monkeypatch.setattr(auth_router, "send_auth_link", capture)
    return links


def csrf(client: TestClient) -> str:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_auth_rate_limit_rejects_excess_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_router, "increment_window", lambda *_args: 11)
    request = Request({"type": "http", "client": ("127.0.0.1", 1234)})
    with pytest.raises(HTTPException) as exc_info:
        enforce_auth_limits(request, "login", "person@example.com")
    assert exc_info.value.status_code == 429


def test_signup_requires_csrf_and_sends_verification_link(
    client: TestClient,
    sent_links: list[tuple[str, str, str]],
) -> None:
    payload = {"email": "  Owner@Example.com ", "password": "a-long-password-123"}
    no_csrf = client.post("/api/auth/signup", json=payload)
    assert no_csrf.status_code == 403

    token = csrf(client)
    response = client.post(
        "/api/auth/signup",
        json=payload,
        headers={"X-RC-CSRF": token},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "owner@example.com"
    assert response.json()["email_verified"] is False
    assert sent_links[0][0] == "owner@example.com"
    assert sent_links[0][2] == "verify_email"


def test_signup_attaches_unexpired_guest_uploads_and_jobs(
    client: TestClient,
    test_session: Session,
) -> None:
    guest_id = "guest-session-to-claim"
    upload_id = uuid4()
    job_id = uuid4()
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    test_session.add(
        Upload(
            id=upload_id,
            guest_id=guest_id,
            user_id=None,
            object_key=f"g:{guest_id}/{upload_id}/sample.pdf",
            filename="sample.pdf",
            content_type="application/pdf",
            size_bytes=100,
            expires_at=expires_at,
        )
    )
    test_session.add(
        Job(
            id=job_id,
            guest_id=guest_id,
            user_id=None,
            tool_slug="merge-pdf",
            state=JobState.SUCCEEDED,
            options={},
            input_upload_ids=[str(upload_id)],
            expires_at=expires_at,
        )
    )
    test_session.commit()
    client.cookies.set("rc_guest", encode_guest_id(guest_id))

    token = csrf(client)
    signup = client.post(
        "/api/auth/signup",
        json={"email": "claim@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )

    assert signup.status_code == 201
    user = test_session.scalar(select(User).where(User.email == "claim@example.com"))
    assert user is not None
    upload = test_session.get(Upload, upload_id)
    job = test_session.get(Job, job_id)
    assert upload is not None and upload.user_id == user.id and upload.guest_id is None
    assert job is not None and job.user_id == user.id and job.guest_id is None


def test_login_rotates_tokens_and_logout_revokes_session(
    client: TestClient,
    sent_links: list[tuple[str, str, str]],
) -> None:
    token = csrf(client)
    response = client.post(
        "/api/auth/signup",
        json={"email": "person@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert response.status_code == 201

    token = csrf(client)
    login = client.post(
        "/api/auth/login",
        json={"email": "PERSON@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert login.status_code == 200
    assert client.cookies.get("rc_session")
    assert client.cookies.get("rc_csrf") != token
    assert client.get("/api/auth/me").json()["email"] == "person@example.com"

    fresh_csrf = client.cookies.get("rc_csrf")
    logout = client.post("/api/auth/logout", headers={"X-RC-CSRF": fresh_csrf})
    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_email_verification_token_is_single_use(
    client: TestClient,
    sent_links: list[tuple[str, str, str]],
) -> None:
    token = csrf(client)
    signup = client.post(
        "/api/auth/signup",
        json={"email": "verify@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert signup.status_code == 201
    verification_token = sent_links[0][1]

    token = csrf(client)
    verified = client.post(
        "/api/auth/verify-email",
        json={"token": verification_token},
        headers={"X-RC-CSRF": token},
    )
    assert verified.status_code == 200
    assert verified.json()["email_verified"] is True

    token = csrf(client)
    replay = client.post(
        "/api/auth/verify-email",
        json={"token": verification_token},
        headers={"X-RC-CSRF": token},
    )
    assert replay.status_code == 400


def test_magic_link_signs_in_without_disclosing_unknown_accounts(
    client: TestClient,
    sent_links: list[tuple[str, str, str]],
) -> None:
    token = csrf(client)
    client.post(
        "/api/auth/signup",
        json={"email": "magic@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )

    token = csrf(client)
    unknown = client.post(
        "/api/auth/magic-link",
        json={"email": "unknown@example.com"},
        headers={"X-RC-CSRF": token},
    )
    assert unknown.status_code == 200
    assert "If the account exists" in unknown.json()["status"]
    assert len(sent_links) == 1

    token = csrf(client)
    requested = client.post(
        "/api/auth/magic-link",
        json={"email": "magic@example.com"},
        headers={"X-RC-CSRF": token},
    )
    assert requested.status_code == 200
    assert sent_links[-1][2] == "magic_link"

    token = csrf(client)
    signed_in = client.post(
        "/api/auth/magic",
        json={"token": sent_links[-1][1]},
        headers={"X-RC-CSRF": token},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["email"] == "magic@example.com"


def test_password_reset_changes_password_and_revokes_existing_session(
    client: TestClient,
    sent_links: list[tuple[str, str, str]],
) -> None:
    token = csrf(client)
    client.post(
        "/api/auth/signup",
        json={"email": "reset@example.com", "password": "old-password-123"},
        headers={"X-RC-CSRF": token},
    )
    token = csrf(client)
    client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "old-password-123"},
        headers={"X-RC-CSRF": token},
    )
    old_session = client.cookies.get("rc_session")

    token = csrf(client)
    requested = client.post(
        "/api/auth/password-reset/request",
        json={"email": "reset@example.com"},
        headers={"X-RC-CSRF": token},
    )
    assert requested.status_code == 200
    assert sent_links[-1][2] == "reset_password"

    token = csrf(client)
    reset = client.post(
        "/api/auth/password-reset",
        json={"token": sent_links[-1][1], "new_password": "new-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert reset.status_code == 204

    client.cookies.set("rc_session", old_session)
    assert client.get("/api/auth/me").status_code == 401

    token = csrf(client)
    rejected = client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "old-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert rejected.status_code == 401
    token = csrf(client)
    accepted = client.post(
        "/api/auth/login",
        json={"email": "reset@example.com", "password": "new-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert accepted.status_code == 200


def test_totp_setup_requires_confirmation_and_login_code(
    client: TestClient,
    sent_links: list[tuple[str, str, str]],
) -> None:
    token = csrf(client)
    client.post(
        "/api/auth/signup",
        json={"email": "mfa@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )
    token = csrf(client)
    client.post(
        "/api/auth/login",
        json={"email": "mfa@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )

    token = csrf(client)
    setup = client.post("/api/auth/totp/setup", headers={"X-RC-CSRF": token})
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["provisioning_uri"].startswith("otpauth://totp/")

    token = csrf(client)
    confirmed = client.post(
        "/api/auth/totp/confirm",
        json={"code": pyotp.TOTP(secret).now()},
        headers={"X-RC-CSRF": token},
    )
    assert confirmed.status_code == 200
    recovery_code = confirmed.json()["recovery_codes"][0]
    assert len(confirmed.json()["recovery_codes"]) == 10

    client.post("/api/auth/logout", headers={"X-RC-CSRF": csrf(client)})
    token = csrf(client)
    no_code = client.post(
        "/api/auth/login",
        json={"email": "mfa@example.com", "password": "a-long-password-123"},
        headers={"X-RC-CSRF": token},
    )
    assert no_code.status_code == 401

    token = csrf(client)
    recovered = client.post(
        "/api/auth/login",
        json={
            "email": "mfa@example.com",
            "password": "a-long-password-123",
            "totp_code": recovery_code,
        },
        headers={"X-RC-CSRF": token},
    )
    assert recovered.status_code == 200

    client.post("/api/auth/logout", headers={"X-RC-CSRF": csrf(client)})
    token = csrf(client)
    replay = client.post(
        "/api/auth/login",
        json={
            "email": "mfa@example.com",
            "password": "a-long-password-123",
            "totp_code": recovery_code,
        },
        headers={"X-RC-CSRF": token},
    )
    assert replay.status_code == 401


def test_google_oauth_uses_state_pkce_and_links_verified_identity(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"google_client_id": "test-google-client"})
    monkeypatch.setattr(auth_router, "get_settings", lambda: settings)
    monkeypatch.setattr(
        auth_router,
        "_exchange_oauth_code",
        lambda *_args: ("google-subject-123", "oauth@example.com", "OAuth User"),
    )

    started = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert started.status_code == 302
    query = parse_qs(urlparse(started.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    state = query["state"][0]

    callback = client.get(
        "/api/auth/oauth/google/callback",
        params={"code": "one-time-code", "state": state},
        follow_redirects=False,
    )

    assert callback.status_code == 302
    assert callback.headers["location"].endswith("/account")
    assert client.cookies.get("rc_session")
    assert client.get("/api/auth/me").json()["email"] == "oauth@example.com"


def test_google_oauth_rejects_state_mismatch(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"google_client_id": "test-google-client"})
    monkeypatch.setattr(auth_router, "get_settings", lambda: settings)
    started = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert started.status_code == 302

    callback = client.get(
        "/api/auth/oauth/google/callback",
        params={"code": "one-time-code", "state": "forged-state"},
        follow_redirects=False,
    )

    assert callback.status_code == 400
