import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import ApiKey, AuthSession, User
from rendercart.auth.router import require_csrf
from rendercart.auth.security import digest_secret
from rendercart.billing.access import user_level
from rendercart.core.access import Level
from rendercart.core.db import get_db
from rendercart.jobs.models import AuditLog

router = APIRouter(prefix="/api/account/api-keys", tags=["developer API"])
Db = Annotated[Session, Depends(get_db)]


class ApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip()


def _session_user(db: Session, raw_session: str | None) -> tuple[User, AuthSession]:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to manage API keys")
    user, session = pair
    if user_level(db, user) < Level.PRO:
        raise HTTPException(
            status_code=402,
            detail="Developer API keys require Pro",
            headers={"X-Paywall": "pro-required"},
        )
    return user, session


@router.get("")
def list_api_keys(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user, _session = _session_user(db, raw_session)
    rows = list(
        db.scalars(
            select(ApiKey)
            .where(ApiKey.user_id == user.id)
            .order_by(ApiKey.created_at.desc())
        )
    )
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "prefix": row.key_prefix,
            "created_at": row.created_at.isoformat(),
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        }
        for row in rows
    ]


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_api_key(
    body: ApiKeyRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _session_user(db, raw_session)
    active_count = int(
        db.scalar(
            select(func.count())
            .select_from(ApiKey)
            .where(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None))
        )
        or 0
    )
    if active_count >= 10:
        raise HTTPException(status_code=409, detail="You can have up to 10 active API keys")
    raw_key = "rc_live_" + secrets.token_urlsafe(32)
    row = ApiKey(
        user_id=user.id,
        name=body.name,
        key_prefix=raw_key[:16],
        key_hash=digest_secret(raw_key),
    )
    db.add(row)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="api_key.created", target=str(row.id)))
    db.commit()
    return {"id": str(row.id), "name": row.name, "prefix": row.key_prefix, "key": raw_key}


@router.delete("/{key_id}", status_code=204, dependencies=[Depends(require_csrf)])
def revoke_api_key(
    key_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> None:
    user, _session = _session_user(db, raw_session)
    row = db.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.add(AuditLog(actor_user_id=user.id, action="api_key.revoked", target=str(row.id)))
        db.commit()
