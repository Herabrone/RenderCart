from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.security import decrypt_secret, encrypt_secret
from rendercart.business import vault as vault_module
from rendercart.business.models import VaultFileShare, VaultPaste, VaultShortLink
from rendercart.core.access import Level, StaffRole
from rendercart.jobs import tasks as job_tasks
from rendercart.jobs.models import AuditLog
from rendercart.registry.loader import load_builtin_registry


def sign_in(
    client: TestClient,
    db: Session,
    role: StaffRole,
    *,
    mfa_verified: bool = True,
) -> User:
    user = User(email=f"{role.value}-{datetime.now(UTC).timestamp()}@example.com", staff_role=role)
    db.add(user)
    db.flush()
    token, _session = auth_service.create_session(
        db, user, "127.0.0.1", "vault-tests", mfa_verified
    )
    db.commit()
    client.cookies.set("rc_session", token)
    return user


def csrf(client: TestClient) -> str:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


@pytest.mark.parametrize("role", [StaffRole.USER, StaffRole.ADMIN])
def test_vault_management_routes_return_404_for_non_owner(
    client: TestClient,
    test_session: Session,
    role: StaffRole,
) -> None:
    sign_in(client, test_session, role)
    token = csrf(client)

    assert client.get("/api/vault/session").status_code == 404
    assert client.get("/api/vault").status_code == 404
    assert client.put("/api/vault/files", content=b"secret").status_code == 404
    assert (
        client.post(
            "/api/vault/pastes",
            json={"content": "hidden route"},
            headers={"X-RC-CSRF": token},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/vault/pastes",
            json={"content": "hidden route"},
        ).status_code
        == 404
    )
    assert client.post("/api/vault/pastes", json={}).status_code == 404
    assert (
        client.delete(
            "/api/vault/pastes/00000000-0000-0000-0000-000000000000",
            headers={"X-RC-CSRF": token},
        ).status_code
        == 404
    )


def test_vault_requires_mfa_for_super_admin(
    client: TestClient,
    test_session: Session,
) -> None:
    sign_in(client, test_session, StaffRole.SUPER_ADMIN, mfa_verified=False)
    assert client.get("/api/vault/session").status_code == 404
    assert client.post("/api/vault/pastes", json={"content": "hidden route"}).status_code == 404
    assert client.put("/api/vault/files", content=b"hidden route").status_code == 404


def test_owner_can_create_encrypted_expiring_shares(
    client: TestClient,
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sign_in(client, test_session, StaffRole.SUPER_ADMIN)
    monkeypatch.setattr(vault_module, "increment_window", lambda *_args: 1)
    monkeypatch.setattr(
        vault_module,
        "validate_public_http_url",
        lambda _url: ("https", "example.com", 443, "93.184.216.34", "/path"),
    )
    token = csrf(client)
    headers = {"X-RC-CSRF": token}

    link = client.post(
        "/api/vault/short-links",
        json={"target_url": "https://example.com/path", "ttl_seconds": 3600},
        headers=headers,
    )
    paste = client.post(
        "/api/vault/pastes",
        json={"content": "private text to share", "ttl_seconds": 86400},
        headers=headers,
    )
    assert link.status_code == 201
    assert paste.status_code == 201

    link_code = urlparse(link.json()["url"]).path.removeprefix("/v/")
    paste_code = urlparse(paste.json()["url"]).path.removeprefix("/p/")
    stored_link = test_session.scalar(
        select(VaultShortLink).where(VaultShortLink.code == link_code)
    )
    stored_paste = test_session.scalar(select(VaultPaste).where(VaultPaste.code == paste_code))
    assert stored_link is not None and "https://example.com/path" not in stored_link.target_url_enc
    assert stored_paste is not None and "private text to share" not in stored_paste.content_enc

    redirect = client.get(f"/v/{link_code}", follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"] == "https://example.com/path"
    shared_text = client.get(f"/p/{paste_code}")
    assert shared_text.status_code == 200
    assert shared_text.text == "private text to share"
    assert shared_text.headers["content-type"].startswith("text/plain")
    assert shared_text.headers["cache-control"] == "no-store"

    actions = set(test_session.scalars(select(AuditLog.action)))
    assert "vault.short_link.created" in actions
    assert "vault.paste.created" in actions


def test_owner_can_create_and_delete_encrypted_file_shares(
    client: TestClient,
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sign_in(client, test_session, StaffRole.SUPER_ADMIN)
    monkeypatch.setattr(vault_module, "increment_window", lambda *_args: 1)
    objects: dict[str, bytes] = {}
    monkeypatch.setattr(
        vault_module,
        "put_vault_object",
        lambda key, body: objects.__setitem__(key, body),
    )
    monkeypatch.setattr(vault_module, "get_vault_object", lambda key: objects[key])
    monkeypatch.setattr(vault_module, "delete_object", lambda _bucket, key: objects.pop(key))
    token = csrf(client)
    response = client.put(
        "/api/vault/files",
        content=b"\x00private-file-payload\xff",
        headers={
            "X-RC-CSRF": token,
            "X-RC-File-Name": "private%20file.bin",
            "X-RC-TTL-Seconds": "3600",
            "Content-Type": "application/octet-stream",
        },
    )
    assert response.status_code == 201
    created = response.json()
    assert created["filename"] == "private file.bin"
    code = urlparse(created["url"]).path.removeprefix("/f/")
    row = test_session.scalar(select(VaultFileShare).where(VaultFileShare.code == code))
    assert row is not None
    stored_key = decrypt_secret(row.object_key_enc)
    assert b"private-file-payload" not in objects[stored_key]

    shared = client.get(f"/f/{code}")
    assert shared.status_code == 200
    assert shared.content == b"\x00private-file-payload\xff"
    assert shared.headers["content-type"] == "application/octet-stream"
    assert shared.headers["x-content-type-options"] == "nosniff"
    assert shared.headers["content-disposition"].startswith("attachment;")

    deleted = client.delete(f"/api/vault/files/{created['id']}", headers={"X-RC-CSRF": token})
    assert deleted.status_code == 204
    assert stored_key not in objects
    assert "vault.file_share.deleted" in set(test_session.scalars(select(AuditLog.action)))


def test_vault_share_links_expire_and_are_removed_by_scheduled_cleanup(
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = User(email="vault-expiry@example.com", staff_role=StaffRole.SUPER_ADMIN)
    test_session.add(owner)
    test_session.flush()
    expired_at = datetime.now(UTC) - timedelta(minutes=1)
    link = VaultShortLink(
        code="expiredlink",
        target_url_enc="encrypted",
        created_by=owner.id,
        expires_at=expired_at,
    )
    paste = VaultPaste(
        code="expiredpaste",
        content_enc="encrypted",
        created_by=owner.id,
        expires_at=expired_at,
    )
    file_share = VaultFileShare(
        code="expiredfile",
        object_key_enc=encrypt_secret("vault-key"),
        filename_enc=encrypt_secret("expired.bin"),
        size_bytes=4,
        created_by=owner.id,
        expires_at=expired_at,
    )
    test_session.add_all([link, paste, file_share])
    test_session.commit()
    factory = sessionmaker(bind=test_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(job_tasks, "SessionLocal", factory)

    deleted_objects: list[tuple[str, str]] = []
    monkeypatch.setattr(
        job_tasks,
        "delete_object",
        lambda bucket, key: deleted_objects.append((bucket, key)),
    )
    assert job_tasks.cleanup_expired_vault_items() == 3
    assert deleted_objects == [("vault", "vault-key")]
    test_session.expire_all()
    assert (
        test_session.scalar(select(VaultShortLink).where(VaultShortLink.code == "expiredlink"))
        is None
    )
    assert test_session.scalar(select(VaultPaste).where(VaultPaste.code == "expiredpaste")) is None
    assert (
        test_session.scalar(select(VaultFileShare).where(VaultFileShare.code == "expiredfile"))
        is None
    )


def test_public_catalog_and_openapi_do_not_expose_vault_management(
    client: TestClient,
) -> None:
    tools = client.get("/api/tools")
    assert tools.status_code == 200
    assert all(tool["category"] != "vault" for tool in tools.json())
    assert client.get("/api/tools/url-shortener").status_code == 404
    assert client.get("/api/tools/pastebin").status_code == 404
    registry = load_builtin_registry()
    assert registry["url-shortener"].restricted and registry["url-shortener"].hidden
    assert registry["url-shortener"].min_level == Level.SUPER_ADMIN
    assert registry["pastebin"].restricted and registry["pastebin"].hidden
    assert registry["pastebin"].min_level == Level.SUPER_ADMIN
    assert registry["temp-file-share"].restricted and registry["temp-file-share"].hidden
    assert registry["temp-file-share"].min_level == Level.SUPER_ADMIN
    paths = client.get("/v1/openapi.json").json()["paths"]
    assert not any("vault" in path for path in paths)
