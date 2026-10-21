from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import quote, unquote
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.router import require_csrf
from rendercart.auth.security import decrypt_bytes, decrypt_secret, encrypt_bytes, encrypt_secret
from rendercart.billing.access import user_level
from rendercart.business.models import VaultFileShare, VaultPaste, VaultShortLink
from rendercart.core.access import Level
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.core.redis import increment_window
from rendercart.jobs.models import AuditLog
from rendercart.jobs.storage import delete_object, get_vault_object, put_vault_object
from rendercart.safety.fetch import UnsafeUrlError, validate_public_http_url

router = APIRouter(prefix="/api/vault", tags=["vault"])
public_router = APIRouter(tags=["vault share links"])
Db = Annotated[Session, Depends(get_db)]
ShortTtl = Literal[3600, 86400, 604800, 2592000]
_ALLOWED_TTL_SECONDS = {3600, 86400, 604800, 2592000}
_MAX_FILE_BYTES = 25 * 1024 * 1024


class ShortLinkRequest(BaseModel):
    target_url: str = Field(min_length=8, max_length=2048)
    ttl_seconds: ShortTtl = 604800

    @field_validator("target_url")
    @classmethod
    def validate_target(cls, value: str) -> str:
        candidate = value.strip()
        try:
            validate_public_http_url(candidate)
        except UnsafeUrlError as exc:
            raise ValueError("Enter a valid public HTTP or HTTPS URL") from exc
        return candidate


class PasteRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    ttl_seconds: ShortTtl = 86_400


def _owner(db: Session, raw_session: str | None) -> User:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=404, detail="Not found")
    user, session = pair
    if user.is_banned or user_level(db, user) < Level.SUPER_ADMIN or not session.mfa_verified:
        raise HTTPException(status_code=404, detail="Not found")
    return user


def _require_vault_owner(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> None:
    _owner(db, raw_session)


def _new_code() -> str:
    return secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16]


def _url(kind: str, code: str) -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/{kind}/{code}"


def _record_audit(db: Session, user_id: UUID, action: str, target: UUID) -> None:
    db.add(AuditLog(actor_user_id=user_id, action=action, target=str(target)))


def _limit_creation(user: User, kind: str) -> None:
    try:
        count = increment_window(f"vault:create:{kind}:{user.id}", 3600)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Vault is temporarily unavailable") from exc
    if count > 30:
        raise HTTPException(status_code=429, detail="Creation limit reached; try again later")


def _short_link_dict(row: VaultShortLink) -> dict[str, object]:
    return {
        "id": str(row.id),
        "url": _url("v", row.code),
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
    }


def _paste_dict(row: VaultPaste) -> dict[str, object]:
    return {
        "id": str(row.id),
        "url": _url("p", row.code),
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
    }


def _file_dict(row: VaultFileShare) -> dict[str, object]:
    return {
        "id": str(row.id),
        "url": _url("f", row.code),
        "filename": decrypt_secret(row.filename_enc),
        "size_bytes": row.size_bytes,
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
    }


@router.get("/session", dependencies=[Depends(_require_vault_owner)])
def vault_session(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, bool]:
    _owner(db, raw_session)
    return {"authorized": True}


@router.get("", dependencies=[Depends(_require_vault_owner)])
def list_vault_items(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, list[dict[str, object]]]:
    user = _owner(db, raw_session)
    now = datetime.now(UTC)
    links = list(
        db.scalars(
            select(VaultShortLink)
            .where(VaultShortLink.created_by == user.id, VaultShortLink.expires_at > now)
            .order_by(VaultShortLink.created_at.desc())
            .limit(100)
        )
    )
    pastes = list(
        db.scalars(
            select(VaultPaste)
            .where(VaultPaste.created_by == user.id, VaultPaste.expires_at > now)
            .order_by(VaultPaste.created_at.desc())
            .limit(100)
        )
    )
    files = list(
        db.scalars(
            select(VaultFileShare)
            .where(VaultFileShare.created_by == user.id, VaultFileShare.expires_at > now)
            .order_by(VaultFileShare.created_at.desc())
            .limit(100)
        )
    )
    return {
        "short_links": [_short_link_dict(row) for row in links],
        "pastes": [_paste_dict(row) for row in pastes],
        "files": [_file_dict(row) for row in files],
    }


@router.post("/short-links", status_code=201, dependencies=[Depends(_require_vault_owner)])
def create_short_link(
    body: ShortLinkRequest,
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _owner(db, raw_session)
    require_csrf(
        request.headers.get("X-RC-CSRF"),
        request.cookies.get(get_settings().csrf_cookie_name),
    )
    now = datetime.now(UTC)
    _limit_creation(user, "short-link")
    active_count = int(
        db.scalar(
            select(func.count())
            .select_from(VaultShortLink)
            .where(VaultShortLink.created_by == user.id, VaultShortLink.expires_at > now)
        )
        or 0
    )
    if active_count >= 100:
        raise HTTPException(status_code=429, detail="The Vault allows up to 100 active short links")
    row = VaultShortLink(
        code=_new_code(),
        target_url_enc=encrypt_secret(body.target_url),
        created_by=user.id,
        expires_at=now + timedelta(seconds=body.ttl_seconds),
    )
    db.add(row)
    db.flush()
    _record_audit(db, user.id, "vault.short_link.created", row.id)
    db.commit()
    return _short_link_dict(row)


@router.post("/pastes", status_code=201, dependencies=[Depends(_require_vault_owner)])
def create_paste(
    body: PasteRequest,
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _owner(db, raw_session)
    require_csrf(
        request.headers.get("X-RC-CSRF"),
        request.cookies.get(get_settings().csrf_cookie_name),
    )
    if len(body.content.encode("utf-8")) > 32_768:
        raise HTTPException(status_code=413, detail="Paste is too large")
    now = datetime.now(UTC)
    _limit_creation(user, "paste")
    active_count = int(
        db.scalar(
            select(func.count())
            .select_from(VaultPaste)
            .where(VaultPaste.created_by == user.id, VaultPaste.expires_at > now)
        )
        or 0
    )
    if active_count >= 100:
        raise HTTPException(status_code=429, detail="The Vault allows up to 100 active text shares")
    row = VaultPaste(
        code=_new_code(),
        content_enc=encrypt_secret(body.content),
        created_by=user.id,
        expires_at=now + timedelta(seconds=body.ttl_seconds),
    )
    db.add(row)
    db.flush()
    _record_audit(db, user.id, "vault.paste.created", row.id)
    db.commit()
    return _paste_dict(row)


@router.put("/files", status_code=201, dependencies=[Depends(_require_vault_owner)])
async def create_file_share(
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _owner(db, raw_session)
    require_csrf(
        request.headers.get("X-RC-CSRF"),
        request.cookies.get(get_settings().csrf_cookie_name),
    )
    raw_filename = request.headers.get("X-RC-File-Name", "download.bin")
    filename = unquote(raw_filename).replace("\\", "/").rsplit("/", 1)[-1].strip()
    if (
        not filename
        or len(filename) > 180
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
    ):
        raise HTTPException(status_code=422, detail="Enter a valid file name")
    raw_ttl = request.headers.get("X-RC-TTL-Seconds", "604800")
    try:
        ttl_seconds = int(raw_ttl)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid share expiration") from exc
    if ttl_seconds not in _ALLOWED_TTL_SECONDS:
        raise HTTPException(status_code=422, detail="Invalid share expiration")
    raw_length = request.headers.get("Content-Length")
    if raw_length is not None and raw_length.isdigit() and int(raw_length) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Files are limited to 25 MB")

    user = db.scalar(select(User).where(User.id == user.id).with_for_update()) or user
    now = datetime.now(UTC)
    _limit_creation(user, "file")
    active_count = int(
        db.scalar(
            select(func.count())
            .select_from(VaultFileShare)
            .where(VaultFileShare.created_by == user.id, VaultFileShare.expires_at > now)
        )
        or 0
    )
    if active_count >= 100:
        raise HTTPException(status_code=429, detail="The Vault allows up to 100 active file shares")

    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > _MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="Files are limited to 25 MB")
    if not content:
        raise HTTPException(status_code=422, detail="Choose a non-empty file")

    object_key = f"{user.id}/{uuid4().hex}"
    row = VaultFileShare(
        code=_new_code(),
        object_key_enc=encrypt_secret(object_key),
        filename_enc=encrypt_secret(filename),
        size_bytes=len(content),
        created_by=user.id,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    object_created = False
    try:
        await asyncio.to_thread(put_vault_object, object_key, encrypt_bytes(bytes(content)))
        object_created = True
        db.add(row)
        db.flush()
        _record_audit(db, user.id, "vault.file_share.created", row.id)
        db.commit()
    except Exception:
        db.rollback()
        if object_created:
            try:
                await asyncio.to_thread(delete_object, get_settings().s3_bucket_vault, object_key)
            except Exception:
                pass
        raise
    return _file_dict(row)


@router.delete(
    "/short-links/{item_id}", status_code=204, dependencies=[Depends(_require_vault_owner)]
)
def delete_short_link(
    item_id: UUID,
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _owner(db, raw_session)
    require_csrf(
        request.headers.get("X-RC-CSRF"),
        request.cookies.get(get_settings().csrf_cookie_name),
    )
    row = db.scalar(select(VaultShortLink).where(VaultShortLink.id == item_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    _record_audit(db, user.id, "vault.short_link.deleted", row.id)
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.delete("/pastes/{item_id}", status_code=204, dependencies=[Depends(_require_vault_owner)])
def delete_paste(
    item_id: UUID,
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _owner(db, raw_session)
    require_csrf(
        request.headers.get("X-RC-CSRF"),
        request.cookies.get(get_settings().csrf_cookie_name),
    )
    row = db.scalar(select(VaultPaste).where(VaultPaste.id == item_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    _record_audit(db, user.id, "vault.paste.deleted", row.id)
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.delete("/files/{item_id}", status_code=204, dependencies=[Depends(_require_vault_owner)])
def delete_file_share(
    item_id: UUID,
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _owner(db, raw_session)
    require_csrf(
        request.headers.get("X-RC-CSRF"),
        request.cookies.get(get_settings().csrf_cookie_name),
    )
    row = db.scalar(select(VaultFileShare).where(VaultFileShare.id == item_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        delete_object(get_settings().s3_bucket_vault, decrypt_secret(row.object_key_enc))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not remove the stored file") from exc
    _record_audit(db, user.id, "vault.file_share.deleted", row.id)
    db.delete(row)
    db.commit()
    return Response(status_code=204)


def _public_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    try:
        count = increment_window(f"vault:share:{ip}", 60)
    except RedisError as exc:
        raise HTTPException(
            status_code=503, detail="Share service is temporarily unavailable"
        ) from exc
    if count > 60:
        raise HTTPException(status_code=429, detail="Too many requests")


@public_router.get("/v/{code}", include_in_schema=False)
def follow_short_link(code: str, request: Request, db: Db) -> Response:
    _public_rate_limit(request)
    row = db.scalar(
        select(VaultShortLink).where(
            VaultShortLink.code == code,
            VaultShortLink.expires_at > datetime.now(UTC),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Link not found or expired")
    try:
        target = decrypt_secret(row.target_url_enc)
        validate_public_http_url(target)
    except (InvalidTag, ValueError, UnsafeUrlError) as exc:
        raise HTTPException(status_code=410, detail="Link destination is unavailable") from exc
    return RedirectResponse(target, status_code=302, headers={"Cache-Control": "no-store"})


@public_router.get("/p/{code}", include_in_schema=False)
def read_paste(code: str, request: Request, db: Db) -> Response:
    _public_rate_limit(request)
    row = db.scalar(
        select(VaultPaste).where(
            VaultPaste.code == code,
            VaultPaste.expires_at > datetime.now(UTC),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Paste not found or expired")
    try:
        content = decrypt_secret(row.content_enc)
    except (InvalidTag, ValueError) as exc:
        raise HTTPException(status_code=410, detail="Paste is unavailable") from exc
    return PlainTextResponse(
        content,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@public_router.get("/f/{code}", include_in_schema=False)
def download_file_share(code: str, request: Request, db: Db) -> Response:
    _public_rate_limit(request)
    row = db.scalar(
        select(VaultFileShare).where(
            VaultFileShare.code == code,
            VaultFileShare.expires_at > datetime.now(UTC),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="File share not found or expired")
    try:
        encrypted = get_vault_object(decrypt_secret(row.object_key_enc))
        content = decrypt_bytes(encrypted)
        filename = decrypt_secret(row.filename_enc)
    except (InvalidTag, ValueError) as exc:
        raise HTTPException(status_code=410, detail="File share is unavailable") from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail="File share is temporarily unavailable"
        ) from exc
    safe_ascii_name = (
        "".join(
            character
            for character in filename
            if 32 <= ord(character) < 127 and character not in '"\\'
        )
        or "download.bin"
    )
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": (
                f"attachment; filename=\"{safe_ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            ),
        },
    )
