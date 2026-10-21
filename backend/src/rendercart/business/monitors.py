from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.router import require_csrf
from rendercart.auth.security import decrypt_secret, encrypt_secret
from rendercart.billing.access import user_level
from rendercart.business.models import UptimeMonitor, UptimeMonitorCheck
from rendercart.core.access import Level
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.jobs.models import AuditLog
from rendercart.safety.fetch import UnsafeUrlError, validate_public_http_url

router = APIRouter(prefix="/api/monitors", tags=["uptime monitors"])
Db = Annotated[Session, Depends(get_db)]
_WEBHOOK_HOSTS = {"discord.com", "hooks.slack.com"}


class MonitorCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=8, max_length=2048)
    webhook_url: str | None = Field(default=None, min_length=20, max_length=2048)
    sms_phone: str | None = Field(default=None, min_length=8, max_length=16)
    sms_consent: bool = False

    @field_validator("name", "url", "webhook_url")
    @classmethod
    def trim_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if any(char in trimmed for char in "\r\n\t\0"):
            raise ValueError("Control characters are not allowed")
        return trimmed

    @field_validator("sms_phone")
    @classmethod
    def validate_sms_phone(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
            raise ValueError("Enter a phone number in international E.164 format")
        return value


class MonitorUpdateRequest(BaseModel):
    active: bool | None = None
    sms_consent: bool | None = None
    sms_phone: str | None = Field(default=None, min_length=8, max_length=16)

    @field_validator("sms_phone")
    @classmethod
    def validate_sms_phone(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\+[1-9][0-9]{7,14}", value):
            raise ValueError("Enter a phone number in international E.164 format")
        return value


def _monitor_user(db: Session, raw_session: str | None) -> User:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to manage uptime monitors")
    user, _session = pair
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is unavailable")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email to create a monitor")
    return user


def _validated_target(value: str) -> str:
    candidate = value.strip()
    if len(candidate) > 2048 or any(char in candidate for char in "\r\n\t\0"):
        raise HTTPException(status_code=422, detail="Enter a valid public website URL")
    try:
        scheme, _host, _port, _ip, _path = validate_public_http_url(candidate)
    except UnsafeUrlError as exc:
        raise HTTPException(
            status_code=422, detail="The monitor must use a public HTTP(S) website"
        ) from exc
    parsed = urlsplit(candidate)
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(status_code=422, detail="URL credentials are not allowed")
    return urlunsplit((scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _validated_webhook(value: str) -> str:
    try:
        scheme, host, port, _ip, _path = validate_public_http_url(value)
        parsed = urlsplit(value)
    except (UnsafeUrlError, ValueError) as exc:
        raise HTTPException(
            status_code=422, detail="Enter a valid Discord or Slack webhook"
        ) from exc
    valid_path = (
        host.casefold() == "discord.com" and parsed.path.startswith("/api/webhooks/")
    ) or (host.casefold() == "hooks.slack.com" and parsed.path.startswith("/services/"))
    if (
        scheme != "https"
        or port != 443
        or not valid_path
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise HTTPException(
            status_code=422,
            detail="Only Discord and Slack HTTPS webhooks are allowed",
        )
    return value


def _monitor_dict(monitor: UptimeMonitor) -> dict[str, object]:
    return {
        "id": str(monitor.id),
        "name": monitor.name,
        "url": monitor.target_url,
        "active": monitor.active,
        "interval_seconds": monitor.interval_seconds,
        "last_checked_at": monitor.last_checked_at.isoformat() if monitor.last_checked_at else None,
        "last_status_code": monitor.last_status_code,
        "last_response_ms": monitor.last_response_ms,
        "last_error_code": monitor.last_error_code,
        "consecutive_failures": monitor.consecutive_failures,
        "has_webhook": monitor.alert_webhook_enc is not None,
        "has_sms": monitor.alert_sms_enc is not None,
    }


@router.get("")
def list_monitors(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user = _monitor_user(db, raw_session)
    monitors = list(
        db.scalars(
            select(UptimeMonitor)
            .where(UptimeMonitor.user_id == user.id)
            .order_by(UptimeMonitor.created_at.desc())
        )
    )
    response: list[dict[str, object]] = []
    for monitor in monitors:
        item = _monitor_dict(monitor)
        item["checks"] = [
            {
                "checked_at": check.checked_at.isoformat(),
                "status_code": check.status_code,
                "response_ms": check.response_ms,
                "error_code": check.error_code,
            }
            for check in db.scalars(
                select(UptimeMonitorCheck)
                .where(UptimeMonitorCheck.monitor_id == monitor.id)
                .order_by(UptimeMonitorCheck.checked_at.desc())
                .limit(30)
            )
        ]
        response.append(item)
    return response


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_monitor(
    body: MonitorCreateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _monitor_user(db, raw_session)
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()) or user
    level = user_level(db, user)
    pro_features = level >= Level.DAY_PASS
    limit = 20 if pro_features else 1
    total = int(
        db.scalar(
            select(func.count())
            .select_from(UptimeMonitor)
            .where(UptimeMonitor.user_id == user.id)
        )
        or 0
    )
    if total >= limit:
        raise HTTPException(status_code=402, detail=f"Your plan allows {limit} uptime monitor(s)")
    if body.webhook_url and not pro_features:
        raise HTTPException(status_code=402, detail="Discord and Slack alerts require Pro")
    if body.sms_phone and not body.sms_consent:
        raise HTTPException(status_code=422, detail="SMS alerts require your explicit consent")
    if body.sms_consent and not body.sms_phone:
        raise HTTPException(status_code=422, detail="Enter a phone number to enable SMS alerts")
    if body.sms_phone and level < Level.PRO:
        raise HTTPException(status_code=402, detail="SMS alerts require Pro")
    settings = get_settings()
    if body.sms_phone and not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from_number
        and settings.monitor_sms_monthly_cap > 0
    ):
        raise HTTPException(status_code=503, detail="SMS alerts are not configured")
    target = _validated_target(body.url)
    webhook = _validated_webhook(body.webhook_url) if body.webhook_url else None
    now = datetime.now(UTC)
    monitor = UptimeMonitor(
        user_id=user.id,
        name=body.name,
        target_url=target,
        alert_email=user.email,
        alert_webhook_enc=encrypt_secret(webhook) if webhook else None,
        alert_sms_enc=encrypt_secret(body.sms_phone) if body.sms_phone else None,
        alert_sms_consent_at=now if body.sms_phone else None,
        active=True,
        interval_seconds=60 if pro_features else 900,
        next_check_at=now,
    )
    db.add(monitor)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action="monitor.created", target=str(monitor.id)))
    db.commit()
    return _monitor_dict(monitor)


@router.patch("/{monitor_id}", dependencies=[Depends(require_csrf)])
def update_monitor(
    monitor_id: UUID,
    body: MonitorUpdateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _monitor_user(db, raw_session)
    monitor = db.scalar(
        select(UptimeMonitor).where(
            UptimeMonitor.id == monitor_id,
            UptimeMonitor.user_id == user.id,
        )
    )
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if body.active is not None:
        monitor.active = body.active
    if body.active:
        monitor.next_check_at = datetime.now(UTC)
    if body.sms_phone is not None and body.sms_consent is not True:
        raise HTTPException(status_code=422, detail="SMS number changes require explicit consent")
    if body.sms_consent is False:
        monitor.alert_sms_enc = None
        monitor.alert_sms_consent_at = None
    elif body.sms_consent is True:
        phone = body.sms_phone or (
            decrypt_secret(monitor.alert_sms_enc) if monitor.alert_sms_enc else None
        )
        if phone is None:
            raise HTTPException(status_code=422, detail="Enter a phone number to enable SMS alerts")
        if user_level(db, user) < Level.PRO:
            raise HTTPException(status_code=402, detail="SMS alerts require Pro")
        settings = get_settings()
        if not (
            settings.twilio_account_sid
            and settings.twilio_auth_token
            and settings.twilio_from_number
            and settings.monitor_sms_monthly_cap > 0
        ):
            raise HTTPException(status_code=503, detail="SMS alerts are not configured")
        if body.sms_phone or monitor.alert_sms_enc is None:
            monitor.alert_sms_consent_at = datetime.now(UTC)
        monitor.alert_sms_enc = encrypt_secret(phone)
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action=(
                "monitor.sms_disabled"
                if body.sms_consent is False
                else "monitor.resumed"
                if body.active
                else "monitor.paused"
            ),
            target=str(monitor.id),
        )
    )
    db.commit()
    return _monitor_dict(monitor)


@router.post("/{monitor_id}/check", status_code=202, dependencies=[Depends(require_csrf)])
def request_monitor_check(
    monitor_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _monitor_user(db, raw_session)
    monitor = db.scalar(
        select(UptimeMonitor).where(
            UptimeMonitor.id == monitor_id,
            UptimeMonitor.user_id == user.id,
        ).with_for_update()
    )
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if not monitor.active:
        raise HTTPException(status_code=409, detail="Resume this monitor before checking it")
    now = datetime.now(UTC)
    if monitor.next_check_at > now:
        retry_after = max(1, int((monitor.next_check_at - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="This monitor has already checked within your plan's interval",
            headers={"Retry-After": str(retry_after)},
        )
    monitor.next_check_at = now + timedelta(seconds=monitor.interval_seconds)
    db.commit()
    from rendercart.jobs.tasks import check_uptime_monitor

    check_uptime_monitor.delay(str(monitor.id))
    return Response(status_code=202)


@router.delete("/{monitor_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_monitor(
    monitor_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _monitor_user(db, raw_session)
    monitor = db.scalar(
        select(UptimeMonitor).where(
            UptimeMonitor.id == monitor_id,
            UptimeMonitor.user_id == user.id,
        )
    )
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.add(AuditLog(actor_user_id=user.id, action="monitor.deleted", target=str(monitor.id)))
    db.delete(monitor)
    db.commit()
    return Response(status_code=204)
