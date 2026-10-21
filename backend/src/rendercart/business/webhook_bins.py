from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.router import require_csrf
from rendercart.auth.security import decrypt_secret, encrypt_secret
from rendercart.billing.access import user_level
from rendercart.business.models import WebhookBin, WebhookBinEvent
from rendercart.core.access import Level
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.core.redis import increment_window
from rendercart.jobs.models import AuditLog

router = APIRouter(prefix="/api/webhook-bins", tags=["webhook tester"])
receiver_router = APIRouter(tags=["webhook tester receiver"])
Db = Annotated[Session, Depends(get_db)]
_TOKEN_HASH = re.compile(r"^[a-f0-9]{64}$")
_MAX_BODY_BYTES = 65_536
_MAX_HEADERS = 30
_MAX_HEADER_BYTES = 8192
_SENSITIVE_HEADER_TERMS = ("auth", "cookie", "token", "secret", "api-key", "password")


class WebhookBinCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name or any(char in name for char in "\r\n\t\0"):
            raise ValueError("Enter a name without control characters")
        return name


def _user(db: Session, raw_session: str | None) -> User:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to manage webhook bins")
    user, _session = pair
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is unavailable")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email to create a webhook bin")
    return user


def _bin_dict(db: Session, webhook_bin: WebhookBin) -> dict[str, object]:
    event_count = int(
        db.scalar(
            select(func.count())
            .select_from(WebhookBinEvent)
            .where(WebhookBinEvent.bin_id == webhook_bin.id)
        )
        or 0
    )
    return {
        "id": str(webhook_bin.id),
        "name": webhook_bin.name,
        "token_prefix": webhook_bin.token_prefix,
        "expires_at": webhook_bin.expires_at.isoformat(),
        "created_at": webhook_bin.created_at.isoformat(),
        "event_count": event_count,
    }


@router.get("")
def list_bins(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user = _user(db, raw_session)
    now = datetime.now(UTC)
    bins = list(
        db.scalars(
            select(WebhookBin)
            .where(WebhookBin.user_id == user.id, WebhookBin.expires_at > now)
            .order_by(WebhookBin.created_at.desc())
        )
    )
    return [_bin_dict(db, webhook_bin) for webhook_bin in bins]


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_bin(
    body: WebhookBinCreateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _user(db, raw_session)
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()) or user
    now = datetime.now(UTC)
    pro_features = user_level(db, user) >= Level.DAY_PASS
    max_bins = 10 if pro_features else 1
    count = int(
        db.scalar(
            select(func.count())
            .select_from(WebhookBin)
            .where(WebhookBin.user_id == user.id, WebhookBin.expires_at > now)
        )
        or 0
    )
    if count >= max_bins:
        raise HTTPException(
            status_code=402,
            detail=f"Your plan allows {max_bins} active webhook bin(s)",
        )
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    expires_at = now + (timedelta(days=7) if pro_features else timedelta(hours=1))
    webhook_bin = WebhookBin(
        user_id=user.id,
        name=body.name,
        token_hash=token_hash,
        token_prefix=token[:8],
        expires_at=expires_at,
    )
    db.add(webhook_bin)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="webhook_bin.created",
            target=str(webhook_bin.id),
        )
    )
    db.commit()
    settings = get_settings()
    return {
        **_bin_dict(db, webhook_bin),
        "endpoint_url": f"{settings.app_base_url.rstrip('/')}/hooks/{token}",
    }


@router.get("/{bin_id}/events")
def list_events(
    bin_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user = _user(db, raw_session)
    webhook_bin = db.scalar(
        select(WebhookBin).where(
            WebhookBin.id == bin_id,
            WebhookBin.user_id == user.id,
            WebhookBin.expires_at > datetime.now(UTC),
        )
    )
    if webhook_bin is None:
        raise HTTPException(status_code=404, detail="Webhook bin not found")
    events = list(
        db.scalars(
            select(WebhookBinEvent)
            .where(WebhookBinEvent.bin_id == webhook_bin.id)
            .order_by(WebhookBinEvent.received_at.desc())
            .limit(25)
        )
    )
    response: list[dict[str, object]] = []
    for event in events:
        try:
            payload = json.loads(decrypt_secret(event.payload_enc))
        except (ValueError, json.JSONDecodeError):
            payload = {"error": "stored_payload_unavailable"}
        response.append(
            {
                "id": str(event.id),
                "method": event.method,
                "received_at": event.received_at.isoformat(),
                "payload": payload,
            }
        )
    return response


@router.delete("/{bin_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_bin(
    bin_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _user(db, raw_session)
    webhook_bin = db.scalar(
        select(WebhookBin).where(WebhookBin.id == bin_id, WebhookBin.user_id == user.id)
    )
    if webhook_bin is None:
        raise HTTPException(status_code=404, detail="Webhook bin not found")
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="webhook_bin.deleted",
            target=str(webhook_bin.id),
        )
    )
    db.delete(webhook_bin)
    db.commit()
    return Response(status_code=204)


@receiver_router.api_route(
    "/hooks/{token}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    name="receive_webhook",
    include_in_schema=False,
)
async def receive_webhook(token: str, request: Request, db: Db) -> Response:
    if len(token) < 32 or len(token) > 64:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    token_hash = hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()
    if not _TOKEN_HASH.fullmatch(token_hash):
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    webhook_bin = db.scalar(
        select(WebhookBin)
        .where(
            WebhookBin.token_hash == token_hash,
            WebhookBin.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    if webhook_bin is None:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    if increment_window(f"webhook-bin:{webhook_bin.id}", 3600) > 120:
        raise HTTPException(
            status_code=429,
            detail="Webhook bin has reached its hourly request limit",
            headers={"Retry-After": "3600"},
        )
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Webhook body exceeds 64 KB")
        chunks.append(chunk)
    filtered_headers: dict[str, str] = {}
    total_header_bytes = 0
    for name, value in request.headers.items():
        header_name = name.casefold()
        if any(term in header_name for term in _SENSITIVE_HEADER_TERMS):
            continue
        if len(filtered_headers) >= _MAX_HEADERS:
            break
        clipped_value = value[:2048]
        total_header_bytes += len(header_name) + len(clipped_value)
        if total_header_bytes > _MAX_HEADER_BYTES:
            break
        filtered_headers[header_name] = clipped_value
    captured = {
        "query": request.url.query[:4096],
        "headers": filtered_headers,
        "body_base64": base64.b64encode(b"".join(chunks)).decode("ascii"),
        "body_utf8": b"".join(chunks).decode("utf-8", errors="replace"),
    }
    event = WebhookBinEvent(
        bin_id=webhook_bin.id,
        method=request.method,
        payload_enc=encrypt_secret(json.dumps(captured, separators=(",", ":"))),
    )
    db.add(event)
    db.flush()
    excess_ids = list(
        db.scalars(
            select(WebhookBinEvent.id)
            .where(WebhookBinEvent.bin_id == webhook_bin.id)
            .order_by(WebhookBinEvent.received_at.desc())
            .offset(100)
        )
    )
    if excess_ids:
        db.execute(delete(WebhookBinEvent).where(WebhookBinEvent.id.in_(excess_ids)))
    db.commit()
    return Response(status_code=202)
