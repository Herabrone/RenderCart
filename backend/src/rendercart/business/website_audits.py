from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.router import require_csrf
from rendercart.auth.security import decrypt_secret, encrypt_secret
from rendercart.billing.access import user_level
from rendercart.business.models import WebsiteAuditReport, WebsiteAuditSchedule
from rendercart.core.access import Level
from rendercart.core.db import get_db
from rendercart.tools.website_audit.manifest import Options

router = APIRouter(prefix="/api/website-audits", tags=["website audits"])
Db = Annotated[Session, Depends(get_db)]


class ScheduleRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    device: str = "mobile"


def _owner(db: Session, raw_session: str | None):
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to manage audit schedules")
    user, _session = pair
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is unavailable")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email to schedule audits")
    if user_level(db, user) < Level.PRO:
        raise HTTPException(
            status_code=402,
            detail="Weekly audit schedules require Pro",
            headers={"X-Paywall": "pro-required"},
        )
    return user


def _schedule_json(row: WebsiteAuditSchedule) -> dict[str, object]:
    return {
        "id": str(row.id),
        "url": decrypt_secret(row.target_url_enc),
        "device": row.device,
        "active": row.active,
        "next_run_at": row.next_run_at.isoformat(),
        "last_job_id": str(row.last_job_id) if row.last_job_id else None,
        "last_error_code": row.last_error_code,
    }


@router.get("")
def list_website_audits(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to view audit history")
    user, _session = pair
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is unavailable")
    if user_level(db, user) < Level.PRO:
        raise HTTPException(status_code=402, detail="Audit history requires Pro")
    reports = list(
        db.scalars(
            select(WebsiteAuditReport)
            .where(WebsiteAuditReport.user_id == user.id)
            .order_by(WebsiteAuditReport.created_at.desc())
            .limit(50)
        )
    )
    return [
        {
            "id": str(report.id),
            "job_id": str(report.job_id) if report.job_id else None,
            "url": decrypt_secret(report.target_url_enc),
            "scores": report.scores,
            "metrics": report.metrics,
            "findings": report.findings,
            "created_at": report.created_at.isoformat(),
        }
        for report in reports
    ]


@router.get("/schedules")
def list_website_audit_schedules(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user = _owner(db, raw_session)
    rows = list(
        db.scalars(
            select(WebsiteAuditSchedule)
            .where(WebsiteAuditSchedule.user_id == user.id)
            .order_by(WebsiteAuditSchedule.created_at.desc())
        )
    )
    return [_schedule_json(row) for row in rows]


@router.post("/schedules", status_code=201, dependencies=[Depends(require_csrf)])
def create_website_audit_schedule(
    body: ScheduleRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _owner(db, raw_session)
    count = int(
        db.scalar(
            select(func.count())
            .select_from(WebsiteAuditSchedule)
            .where(WebsiteAuditSchedule.user_id == user.id)
        )
        or 0
    )
    if count >= 5:
        raise HTTPException(status_code=409, detail="You can have up to five weekly audits")
    try:
        options = Options.model_validate(body.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Enter a public HTTPS URL and device") from exc
    now = datetime.now(UTC)
    row = WebsiteAuditSchedule(
        user_id=user.id,
        target_url_enc=encrypt_secret(options.url),
        device=options.device,
        active=True,
        next_run_at=now + timedelta(days=7),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _schedule_json(row)


@router.delete("/schedules/{schedule_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_website_audit_schedule(
    schedule_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user = _owner(db, raw_session)
    row = db.scalar(
        select(WebsiteAuditSchedule).where(
            WebsiteAuditSchedule.id == schedule_id,
            WebsiteAuditSchedule.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Audit schedule not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
