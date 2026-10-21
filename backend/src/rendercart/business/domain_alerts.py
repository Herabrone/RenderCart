from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.router import require_csrf
from rendercart.billing.access import user_level
from rendercart.business.models import DomainExpiryAlert
from rendercart.core.access import Level
from rendercart.core.db import get_db
from rendercart.jobs.models import AuditLog
from rendercart.safety.fetch import UnsafeUrlError, validate_public_http_url

router = APIRouter(prefix="/api/domain-alerts", tags=["domain alerts"])
Db = Annotated[Session, Depends(get_db)]
_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)


class DomainAlertCreateRequest(BaseModel):
    domain: str = Field(min_length=3, max_length=253)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        candidate = value.strip().rstrip(".").casefold()
        if any(char in candidate for char in "/:@?#\r\n\t\0"):
            raise ValueError("Enter a domain name without a scheme or path")
        try:
            ascii_domain = candidate.encode("idna").decode("ascii")
        except ValueError:
            raise ValueError("Enter a valid internationalized domain name") from None
        try:
            ipaddress.ip_address(ascii_domain)
        except ValueError:
            pass
        else:
            raise ValueError("Enter a domain name, not an IP address")
        labels = ascii_domain.split(".")
        if len(labels) < 2 or any(not _DOMAIN_LABEL.fullmatch(label) for label in labels):
            raise ValueError("Enter a fully qualified domain name")
        try:
            validate_public_http_url(f"https://{ascii_domain}/")
        except UnsafeUrlError as exc:
            raise ValueError("Domain must resolve only to public addresses") from exc
        return ascii_domain


class DomainAlertUpdateRequest(BaseModel):
    active: bool


def _user(db: Session, raw_session: str | None) -> User:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to manage domain alerts")
    user, _session = pair
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is unavailable")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email to create an alert")
    return user


def _alert_dict(alert: DomainExpiryAlert) -> dict[str, object]:
    return {
        "id": str(alert.id),
        "domain": alert.domain,
        "active": alert.active,
        "last_checked_at": alert.last_checked_at.isoformat() if alert.last_checked_at else None,
        "tls_expires_at": alert.tls_expires_at.isoformat() if alert.tls_expires_at else None,
        "domain_expires_at": (
            alert.domain_expires_at.isoformat() if alert.domain_expires_at else None
        ),
        "tls_error_code": alert.tls_error_code,
        "domain_error_code": alert.domain_error_code,
    }


@router.get("")
def list_domain_alerts(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user = _user(db, raw_session)
    return [
        _alert_dict(alert)
        for alert in db.scalars(
            select(DomainExpiryAlert)
            .where(DomainExpiryAlert.user_id == user.id)
            .order_by(DomainExpiryAlert.created_at.desc())
        )
    ]


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_domain_alert(
    body: DomainAlertCreateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _user(db, raw_session)
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()) or user
    paid = user_level(db, user) >= Level.DAY_PASS
    count = int(
        db.scalar(
            select(func.count())
            .select_from(DomainExpiryAlert)
            .where(DomainExpiryAlert.user_id == user.id)
        )
        or 0
    )
    if not paid and count >= 1:
        raise HTTPException(status_code=402, detail="Your plan allows one domain expiry alert")
    existing = db.scalar(
        select(DomainExpiryAlert.id).where(
            DomainExpiryAlert.user_id == user.id,
            DomainExpiryAlert.domain == body.domain,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="This domain already has an alert")
    now = datetime.now(UTC)
    alert = DomainExpiryAlert(
        user_id=user.id,
        domain=body.domain,
        alert_email=user.email,
        active=True,
        interval_seconds=86_400,
        next_check_at=now,
    )
    db.add(alert)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="domain_alert.created", target=str(alert.id)))
    db.commit()
    return _alert_dict(alert)


@router.patch("/{alert_id}", dependencies=[Depends(require_csrf)])
def update_domain_alert(
    alert_id: UUID,
    body: DomainAlertUpdateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _user(db, raw_session)
    alert = db.scalar(
        select(DomainExpiryAlert).where(
            DomainExpiryAlert.id == alert_id,
            DomainExpiryAlert.user_id == user.id,
        )
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="Domain alert not found")
    alert.active = body.active
    if body.active:
        alert.next_check_at = datetime.now(UTC)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="domain_alert.resumed" if body.active else "domain_alert.paused",
            target=str(alert.id),
        )
    )
    db.commit()
    return _alert_dict(alert)


@router.delete("/{alert_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_domain_alert(
    alert_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _user(db, raw_session)
    alert = db.scalar(
        select(DomainExpiryAlert).where(
            DomainExpiryAlert.id == alert_id,
            DomainExpiryAlert.user_id == user.id,
        )
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="Domain alert not found")
    db.add(AuditLog(actor_user_id=user.id, action="domain_alert.deleted", target=str(alert.id)))
    db.delete(alert)
    db.commit()
    return Response(status_code=204)
