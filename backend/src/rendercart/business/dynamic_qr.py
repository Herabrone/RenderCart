from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import AuthSession, User
from rendercart.auth.router import require_csrf
from rendercart.billing.access import user_level
from rendercart.business.models import DynamicQrCode, DynamicQrReport, DynamicQrScan
from rendercart.core.access import Level
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.core.redis import increment_window, redis_client
from rendercart.jobs.models import AuditLog
from rendercart.safety.fetch import UnsafeUrlError, validate_public_http_url

router = APIRouter(prefix="/api/business/dynamic-qr", tags=["business tools"])
public_router = APIRouter(tags=["dynamic QR redirects"])
Db = Annotated[Session, Depends(get_db)]
_COUNTRY = re.compile(r"^[A-Z]{2}$")
_ALLOWED_THREATS = (
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
)


class QrCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    target_url: str = Field(min_length=8, max_length=2048)

    @field_validator("name", "target_url")
    @classmethod
    def trim_value(cls, value: str) -> str:
        return value.strip()


class QrUpdateRequest(QrCreateRequest):
    pass


class AbuseReportRequest(BaseModel):
    message: str | None = Field(default=None, max_length=1000)


class AbuseReportStatusRequest(BaseModel):
    resolved: bool


def _user_and_session(db: Session, raw_session: str | None) -> tuple[User, AuthSession]:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to manage dynamic QR codes")
    return pair


def _validate_destination(raw_url: str) -> str:
    candidate = raw_url.strip()
    if len(candidate) > 2048 or any(char in candidate for char in "\r\n\t\0"):
        raise HTTPException(status_code=422, detail="Enter a valid public website URL")
    try:
        validate_public_http_url(candidate)
    except UnsafeUrlError as exc:
        raise HTTPException(
            status_code=422,
            detail="The target must be an HTTP(S) URL on a public host",
        ) from exc
    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Enter an HTTP(S) website URL")
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(status_code=422, detail="URL credentials are not allowed")
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, "")
    )


def _web_risk_flagged(url: str) -> bool:
    settings = get_settings()
    api_key = settings.google_web_risk_api_key
    if api_key is None or not api_key.get_secret_value():
        raise HTTPException(
            status_code=503,
            detail="Dynamic QR safety checks are not configured yet",
        )
    cache_key = "webrisk:" + hashlib.sha256(url.encode("utf-8")).hexdigest()
    cached = redis_client.get(cache_key)
    if cached in {"safe", "unsafe"}:
        return bool(cached == "unsafe")
    query = urllib.parse.urlencode(
        [("threatTypes", threat) for threat in _ALLOWED_THREATS]
        + [("uri", url), ("key", api_key.get_secret_value())]
    )
    request = urllib.request.Request(
        f"https://webrisk.googleapis.com/v1/uris:search?{query}",
        headers={"Accept": "application/json", "User-Agent": "RenderCart/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                raise ValueError("lookup_failed")
            result = json.loads(response.read(64_000))
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=503, detail="URL safety check is temporarily unavailable"
        ) from exc
    threat = result.get("threat") if isinstance(result, dict) else None
    flagged = isinstance(threat, dict) and bool(threat.get("threatTypes"))
    ttl_seconds = 900
    if isinstance(threat, dict) and isinstance(threat.get("expireTime"), str):
        try:
            expires = datetime.fromisoformat(threat["expireTime"].replace("Z", "+00:00"))
            ttl_seconds = max(1, min(86_400, int((expires - datetime.now(UTC)).total_seconds())))
        except ValueError:
            pass
    redis_client.set(cache_key, "unsafe" if flagged else "safe", ex=ttl_seconds)
    return flagged


def _check_target(url: str) -> str:
    target = _validate_destination(url)
    if _web_risk_flagged(target):
        raise HTTPException(
            status_code=422,
            detail="This target was flagged by the Web Risk URL safety check",
        )
    return target


def _scan_device(user_agent: str) -> str:
    normalized = user_agent.lower()
    if any(token in normalized for token in ("ipad", "tablet", "kindle")):
        return "tablet"
    if any(token in normalized for token in ("mobile", "iphone", "android")):
        return "mobile"
    if normalized:
        return "desktop"
    return "unknown"


def _scan_country(request: Request) -> str:
    if not get_settings().dynamic_qr_trust_country_header:
        return "ZZ"
    candidate = request.headers.get("cf-ipcountry", "").upper()
    return candidate if _COUNTRY.fullmatch(candidate) else "ZZ"


@router.get("")
def list_codes(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user, _session = _user_and_session(db, raw_session)
    codes = list(
        db.scalars(
            select(DynamicQrCode)
            .where(DynamicQrCode.user_id == user.id)
            .order_by(DynamicQrCode.created_at.desc())
        )
    )
    return [
        {
            "id": str(item.id),
            "code": item.code,
            "name": item.name,
            "target_url": item.target_url,
            "enabled": item.enabled,
            "scan_count": item.scan_count,
            "created_at": item.created_at.isoformat(),
            "scans": [
                {
                    "country": scan.country_code,
                    "device": scan.device_type,
                    "scanned_at": scan.scanned_at.isoformat(),
                }
                for scan in db.scalars(
                    select(DynamicQrScan)
                    .where(DynamicQrScan.qr_id == item.id)
                    .order_by(DynamicQrScan.scanned_at.desc())
                    .limit(100)
                )
            ],
        }
        for item in codes
    ]


@router.post("", status_code=201, dependencies=[Depends(require_csrf)])
def create_code(
    body: QrCreateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _user_and_session(db, raw_session)
    level = user_level(db, user)
    if increment_window(f"dynamic-qr:create:user:{user.id}", 86_400) > 20:
        raise HTTPException(status_code=429, detail="Too many dynamic QR codes created today")
    existing_count = int(
        db.scalar(select(DynamicQrCode.id).where(DynamicQrCode.user_id == user.id).limit(1000))
        is not None
    )
    if level < Level.PRO and existing_count:
        raise HTTPException(
            status_code=402,
            detail="Free accounts can create one dynamic QR code. Pro unlocks more.",
            headers={"X-Paywall": "pro-required"},
        )
    target = _check_target(body.target_url)
    item = DynamicQrCode(
        user_id=user.id,
        code=secrets.token_urlsafe(12),
        name=body.name,
        target_url=target,
    )
    db.add(item)
    db.add(AuditLog(actor_user_id=user.id, action="dynamic_qr.created", target=str(item.id)))
    db.commit()
    db.refresh(item)
    return {
        "id": str(item.id),
        "code": item.code,
        "name": item.name,
        "target_url": item.target_url,
        "enabled": item.enabled,
        "scan_count": item.scan_count,
        "redirect_url": f"{get_settings().app_base_url.rstrip('/')}/q/{item.code}",
    }


@router.put("/{qr_id}", dependencies=[Depends(require_csrf)])
def update_code(
    qr_id: UUID,
    body: QrUpdateRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _user_and_session(db, raw_session)
    item = db.scalar(
        select(DynamicQrCode).where(DynamicQrCode.id == qr_id, DynamicQrCode.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Dynamic QR code not found")
    item.target_url = _check_target(body.target_url)
    item.name = body.name
    item.updated_at = datetime.now(UTC)
    db.add(AuditLog(actor_user_id=user.id, action="dynamic_qr.target_updated", target=str(item.id)))
    db.commit()
    return {
        "id": str(item.id),
        "code": item.code,
        "name": item.name,
        "target_url": item.target_url,
        "enabled": item.enabled,
        "scan_count": item.scan_count,
        "redirect_url": f"{get_settings().app_base_url.rstrip('/')}/q/{item.code}",
    }


@router.delete("/{qr_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_code(
    qr_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user, _session = _user_and_session(db, raw_session)
    item = db.scalar(
        select(DynamicQrCode).where(DynamicQrCode.id == qr_id, DynamicQrCode.user_id == user.id)
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Dynamic QR code not found")
    db.add(AuditLog(actor_user_id=user.id, action="dynamic_qr.deleted", target=str(item.id)))
    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/admin/{qr_id}/disable", dependencies=[Depends(require_csrf)])
def admin_disable_code(
    qr_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, bool]:
    user, session = _user_and_session(db, raw_session)
    if user_level(db, user) < Level.ADMIN or not session.mfa_verified:
        raise HTTPException(status_code=404, detail="Not found")
    item = db.get(DynamicQrCode, qr_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Not found")
    item.enabled = False
    db.add(AuditLog(actor_user_id=user.id, action="dynamic_qr.admin_disabled", target=str(item.id)))
    db.commit()
    return {"enabled": False}


@router.get("/admin/reports")
def admin_reports(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user, session = _user_and_session(db, raw_session)
    if user_level(db, user) < Level.ADMIN or not session.mfa_verified:
        raise HTTPException(status_code=404, detail="Not found")
    records = list(
        db.scalars(
            select(DynamicQrReport)
            .order_by(DynamicQrReport.status, DynamicQrReport.created_at.desc())
            .limit(500)
        )
    )
    return [
        {
            "id": str(row.id),
            "qr_id": str(row.qr_id) if row.qr_id else None,
            "code": row.qr_code,
            "target_url": row.target_url,
            "message": row.message,
            "status": row.status,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "created_at": row.created_at.isoformat(),
        }
        for row in records
    ]


@router.patch("/admin/reports/{report_id}", dependencies=[Depends(require_csrf)])
def set_report_status(
    report_id: UUID,
    body: AbuseReportStatusRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, session = _user_and_session(db, raw_session)
    if user_level(db, user) < Level.ADMIN or not session.mfa_verified:
        raise HTTPException(status_code=404, detail="Not found")
    report = db.get(DynamicQrReport, report_id, with_for_update=True)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = "resolved" if body.resolved else "open"
    report.resolved_by = user.id if body.resolved else None
    report.resolved_at = datetime.now(UTC) if body.resolved else None
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="dynamic_qr.report_resolved" if body.resolved else "dynamic_qr.report_reopened",
            target=str(report.id),
            details={"qr_code": report.qr_code},
        )
    )
    db.commit()
    return {
        "id": str(report.id),
        "status": report.status,
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
    }


@public_router.get("/q/{code}")
def open_code(code: str, request: Request, db: Db) -> RedirectResponse:
    item = db.scalar(
        select(DynamicQrCode).where(DynamicQrCode.code == code, DynamicQrCode.enabled.is_(True))
    )
    if item is None:
        raise HTTPException(status_code=404, detail="QR code not found")
    try:
        target = _validate_destination(item.target_url)
    except HTTPException as exc:
        item.enabled = False
        db.commit()
        raise HTTPException(status_code=410, detail="This QR code has been disabled") from exc
    if _web_risk_flagged(target):
        item.enabled = False
        db.add(AuditLog(action="dynamic_qr.disabled_by_url_safety", target=str(item.id)))
        db.commit()
        raise HTTPException(status_code=410, detail="This QR code has been disabled")
    db.execute(
        update(DynamicQrCode)
        .where(DynamicQrCode.id == item.id)
        .values(scan_count=DynamicQrCode.scan_count + 1, updated_at=DynamicQrCode.updated_at)
    )
    db.add(
        DynamicQrScan(
            qr_id=item.id,
            country_code=_scan_country(request),
            device_type=_scan_device(request.headers.get("user-agent", "")),
        )
    )
    db.commit()
    return RedirectResponse(f"/q/{item.code}/continue", status_code=302)


@public_router.get("/q/{code}/continue", response_class=HTMLResponse)
def continue_code(code: str, db: Db) -> HTMLResponse:
    item = db.scalar(
        select(DynamicQrCode).where(DynamicQrCode.code == code, DynamicQrCode.enabled.is_(True))
    )
    if item is None:
        raise HTTPException(status_code=404, detail="QR code not found")
    target = _validate_destination(item.target_url)
    if _web_risk_flagged(target):
        item.enabled = False
        db.add(AuditLog(action="dynamic_qr.disabled_by_url_safety", target=str(item.id)))
        db.commit()
        raise HTTPException(status_code=410, detail="This QR code has been disabled")
    parsed = urllib.parse.urlsplit(target)
    safe_target = html.escape(target, quote=True)
    safe_host = html.escape(parsed.hostname or target)
    report_path = f"/q/{html.escape(code, quote=True)}/report"
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Leaving RenderCart</title>'
        '<main style="font:16px system-ui;max-width:40rem;margin:12vh auto;padding:2rem">'
        "<h1>You are opening an external website</h1><p>This QR code points to <strong>"
        f"{safe_host}</strong>.</p>"
        f'<p><a rel="noopener noreferrer" href="{safe_target}">Continue to website</a></p>'
        f'<p><a href="{report_path}">Report this QR code</a></p></main></html>',
        headers={"X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"},
    )


@public_router.get("/q/{code}/report", response_class=HTMLResponse)
def report_form(code: str, db: Db) -> HTMLResponse:
    exists = db.scalar(select(DynamicQrCode.id).where(DynamicQrCode.code == code))
    if exists is None:
        raise HTTPException(status_code=404, detail="QR code not found")
    safe_code = html.escape(code, quote=True)
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" '
        'content="width=device-width,initial-scale=1"><title>Report QR code</title>'
        '<main style="font:16px system-ui;max-width:40rem;margin:12vh auto;padding:2rem">'
        '<h1>Report this QR code</h1><form method="post" action="/q/'
        f'{safe_code}/report"><label>Why should we review it? '
        '<textarea name="message" maxlength="1000"></textarea>'
        '</label><button type="submit">Send report</button></form></main></html>',
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )


@public_router.post("/q/{code}/report", response_class=HTMLResponse)
async def submit_report(code: str, request: Request, db: Db) -> HTMLResponse:
    ip = request.client.host if request.client else "unknown"
    if increment_window(f"dynamic-qr:report:{ip}", 3600) > 5:
        raise HTTPException(status_code=429, detail="Too many reports")
    item = db.scalar(select(DynamicQrCode).where(DynamicQrCode.code == code))
    if item is None:
        raise HTTPException(status_code=404, detail="QR code not found")
    message = ""
    raw = await request.body()
    if len(raw) <= 4096:
        fields = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        message = fields.get("message", [""])[0].strip()[:1000]
    db.add(
        DynamicQrReport(
            qr_id=item.id,
            qr_code=item.code,
            target_url=item.target_url,
            message=message or None,
        )
    )
    db.commit()
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Report received</title>'
        '<main style="font:16px system-ui;max-width:40rem;margin:12vh auto;padding:2rem">'
        "<h1>Thank you</h1><p>Your report was sent for review.</p></main></html>",
        headers={"X-Robots-Tag": "noindex, nofollow"},
    )
