from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from rendercart.admin.gpu_metrics import gpu_health_snapshot
from rendercart.ai.models import AIUsage
from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.router import require_csrf
from rendercart.billing.access import user_level
from rendercart.billing.models import Purchase
from rendercart.core.access import Level, StaffRole
from rendercart.core.db import get_db
from rendercart.jobs.models import (
    AuditLog,
    CreditAccount,
    CreditLedger,
    CreditLot,
    Job,
    JobState,
    ToolOverride,
)
from rendercart.registry.loader import load_builtin_registry
from rendercart.registry.models import Limit

router = APIRouter(prefix="/api/admin", tags=["admin"])
Db = Annotated[Session, Depends(get_db)]
registry = load_builtin_registry()


class BanRequest(BaseModel):
    banned: bool


class CreditGrantRequest(BaseModel):
    amount: int = Field(gt=0, le=100_000)
    reason: str = Field(min_length=3, max_length=255)


class RoleRequest(BaseModel):
    role: Literal["user", "admin"]


class ToolOverrideRequest(BaseModel):
    enabled: bool | None = None
    limits: dict[str, dict[str, object]] | None = None
    prices: dict[str, object] | None = None


def _staff(
    db: Session,
    raw_session: str | None,
    *,
    super_admin: bool = False,
) -> User:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=404, detail="Not found")
    user, session = pair
    required = Level.SUPER_ADMIN if super_admin else Level.ADMIN
    if user_level(db, user) < required or not session.mfa_verified:
        raise HTTPException(status_code=404, detail="Not found")
    return user


@router.get("/overview")
def overview(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    actor = _staff(db, raw_session)
    now = datetime.now(UTC)
    users = int(db.scalar(select(func.count()).select_from(User)) or 0)
    jobs = int(db.scalar(select(func.count()).select_from(Job)) or 0)
    queued = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.state == JobState.QUEUED)) or 0
    )
    running = int(
        db.scalar(select(func.count()).select_from(Job).where(Job.state == JobState.RUNNING)) or 0
    )
    revenue = int(
        db.scalar(
            select(func.coalesce(func.sum(Purchase.amount_cents), 0)).where(
                Purchase.status == "paid"
            )
        )
        or 0
    )
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ai_month_usd = db.scalar(
        select(func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0)).where(
            AIUsage.created_at >= month_start
        )
    )
    return {
        "actor_role": actor.staff_role.value,
        "users": users,
        "jobs_total": jobs,
        "jobs_queued": queued,
        "jobs_running": running,
        "gross_revenue_cents": revenue,
        "ai_estimated_cost_usd_month": str(ai_month_usd or 0),
    }


@router.get("/gpu")
def gpu_health(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    _staff(db, raw_session)
    return gpu_health_snapshot()


@router.get("/users")
def list_users(
    db: Db,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    _staff(db, raw_session)
    statement = select(User).order_by(User.created_at.desc())
    if q.strip():
        pattern = f"%{q.strip()[:160]}%"
        statement = statement.where(
            or_(User.email.ilike(pattern), User.display_name.ilike(pattern))
        )
    rows = list(db.scalars(statement.offset(max(0, offset)).limit(max(1, min(limit, 100)))))
    return [
        {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "email_verified": user.email_verified_at is not None,
            "staff_role": user.staff_role.value,
            "level": user_level(db, user).name.lower(),
            "is_banned": user.is_banned,
            "created_at": user.created_at.isoformat(),
        }
        for user in rows
    ]


@router.patch("/users/{user_id}/ban", dependencies=[Depends(require_csrf)])
def set_user_ban(
    user_id: UUID,
    body: BanRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, bool]:
    actor = _staff(db, raw_session)
    user = db.get(User, user_id)
    if user is None or user.staff_role == StaffRole.SUPER_ADMIN or user.id == actor.id:
        raise HTTPException(status_code=404, detail="Not found")
    user.is_banned = body.banned
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="user.banned" if body.banned else "user.unbanned",
            target=str(user.id),
        )
    )
    db.commit()
    return {"is_banned": user.is_banned}


@router.post("/users/{user_id}/credits", status_code=201, dependencies=[Depends(require_csrf)])
def grant_user_credits(
    user_id: UUID,
    body: CreditGrantRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, int]:
    actor = _staff(db, raw_session)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    account = db.get(CreditAccount, user.id, with_for_update=True)
    if account is None:
        account = CreditAccount(user_id=user.id, balance=0, held=0)
        db.add(account)
    account.balance += body.amount
    ledger_id = uuid4()
    db.add(
        CreditLedger(
            id=ledger_id,
            user_id=user.id,
            amount=body.amount,
            kind="grant",
            note=body.reason.strip()[:255],
        )
    )
    db.add(
        CreditLot(
            user_id=user.id,
            source_ledger_id=ledger_id,
            total=body.amount,
            remaining=body.amount,
            held=0,
        )
    )
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="credits.granted",
            target=str(user.id),
            details={"amount": body.amount, "reason": body.reason[:255]},
        )
    )
    db.commit()
    return {"amount": body.amount}


@router.patch("/users/{user_id}/role", dependencies=[Depends(require_csrf)])
def set_user_role(
    user_id: UUID,
    body: RoleRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, str]:
    actor = _staff(db, raw_session, super_admin=True)
    user = db.get(User, user_id)
    if user is None or user.staff_role == StaffRole.SUPER_ADMIN:
        raise HTTPException(status_code=404, detail="Not found")
    role = StaffRole(body.role)
    if role == StaffRole.ADMIN and user.email_verified_at is None:
        raise HTTPException(
            status_code=422,
            detail="Verify the user's email before granting admin access",
        )
    user.staff_role = role
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="user.role_changed",
            target=str(user.id),
            details={"role": role.value},
        )
    )
    db.commit()
    return {"role": user.staff_role.value}


@router.get("/jobs")
def list_recent_jobs(
    db: Db,
    limit: int = 100,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    _staff(db, raw_session)
    rows = list(
        db.scalars(select(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 500))))
    )
    return [
        {
            "job_id": str(job.id),
            "user_id": str(job.user_id) if job.user_id else None,
            "tool_slug": job.tool_slug,
            "state": job.state.value,
            "progress": job.progress,
            "error_code": job.error_code,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        for job in rows
    ]


@router.get("/tools")
def list_tool_controls(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    _staff(db, raw_session)
    controls: list[dict[str, object]] = []
    for slug, tool in registry.items():
        if tool.restricted:
            continue
        override = db.get(ToolOverride, slug)
        controls.append(
            {
                "slug": slug,
                "name": tool.name,
                "enabled": override.enabled if override else True,
                "limits": override.limits if override else {},
                "prices": override.prices if override else {},
                "job_tier": tool.job_tier.value if tool.job_tier else None,
                "single_job_price_cents": tool.single_job_price_cents,
            }
        )
    return controls


@router.put("/tools/{slug}", dependencies=[Depends(require_csrf)])
def update_tool_controls(
    slug: str,
    body: ToolOverrideRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    actor = _staff(db, raw_session)
    tool = registry.get(slug)
    if tool is None or tool.restricted:
        raise HTTPException(status_code=404, detail="Tool not found")
    override = db.get(ToolOverride, slug)
    if override is None:
        override = ToolOverride(slug=slug, enabled=True, limits={}, prices={})
        db.add(override)
    if body.enabled is not None:
        override.enabled = body.enabled
    if body.limits is not None:
        validated: dict[str, object] = {}
        for level_name, limit_data in body.limits.items():
            if level_name not in {level.name.lower() for level in Level}:
                raise HTTPException(status_code=422, detail="Unknown access level")
            validated[level_name] = Limit.model_validate(limit_data).model_dump(mode="json")
        override.limits = validated
    if body.prices is not None:
        allowed_tiers = {"job_s", "job_m", "job_l"}
        if set(body.prices) - allowed_tiers or any(
            not isinstance(value, int) or value < 1 for value in body.prices.values()
        ):
            raise HTTPException(status_code=422, detail="Prices must be positive integer cents")
        override.prices = body.prices
    override.updated_by = actor.id
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            action="tool.override_updated",
            target=slug,
            details={
                "enabled": override.enabled,
                "limits_changed": body.limits is not None,
                "prices_changed": body.prices is not None,
            },
        )
    )
    db.commit()
    return {
        "slug": slug,
        "enabled": override.enabled,
        "limits": override.limits,
        "prices": override.prices,
    }


@router.get("/audit")
def list_audit_log(
    db: Db,
    limit: int = 100,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    _staff(db, raw_session)
    rows = list(
        db.scalars(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 500)))
        )
    )
    return [
        {
            "id": str(row.id),
            "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
            "action": row.action,
            "target": row.target,
            "details": row.details,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
