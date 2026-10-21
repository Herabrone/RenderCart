from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, TypeVar, cast
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.models import AuthSession, User
from rendercart.auth.router import require_csrf
from rendercart.auth.security import decrypt_secret, encrypt_secret
from rendercart.billing.access import user_level
from rendercart.business.models import (
    RecurringInvoiceSchedule,
    SavedInvoiceClient,
    SavedInvoiceItem,
)
from rendercart.business.numbering import reserve_number
from rendercart.core.access import Level
from rendercart.core.db import get_db
from rendercart.jobs.models import AuditLog
from rendercart.tools.business.invoice.run import InvoicePayload

router = APIRouter(prefix="/api/business/invoice", tags=["business tools"])
Db = Annotated[Session, Depends(get_db)]
Record = TypeVar("Record", SavedInvoiceClient, SavedInvoiceItem)


class ClientPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(default="", max_length=320)
    address: str = Field(default="", max_length=500)

    @field_validator("name", "email", "address")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class ItemPayload(BaseModel):
    description: str = Field(min_length=1, max_length=240)
    unit_price: str = Field(min_length=1, max_length=32)

    @field_validator("description", "unit_price")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class NumberRequest(BaseModel):
    document_type: str = Field(pattern=r"^(invoice|quote|receipt)$")


class RecurringRequest(BaseModel):
    interval: Literal["weekly", "monthly"]
    invoice: dict[str, object]


class RecurringActiveRequest(BaseModel):
    active: bool


def _owner(db: Session, raw_session: str | None) -> tuple[User, AuthSession]:
    pair = auth_service.get_session_user(db, raw_session)
    if pair is None:
        raise HTTPException(status_code=401, detail="Sign in to save invoice contacts and items")
    return pair


def _pack(payload: BaseModel) -> str:
    return encrypt_secret(payload.model_dump_json())


def _unpack(record: SavedInvoiceClient | SavedInvoiceItem) -> dict[str, object]:
    try:
        data = json.loads(decrypt_secret(record.encrypted_data))
        if not isinstance(data, dict):
            raise ValueError("invalid_saved_record")
        return cast(dict[str, object], data)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Saved invoice data could not be read") from exc


def _list_records(  # noqa: UP047
    db: Session,
    user: User,
    record_type: type[Record],
    payload_type: type[BaseModel],
) -> list[dict[str, object]]:
    rows = list(
        db.scalars(
            select(record_type)
            .where(record_type.user_id == user.id)
            .order_by(record_type.created_at.desc())
        )
    )
    records: list[dict[str, object]] = []
    for row in rows:
        parsed = payload_type.model_validate(_unpack(row)).model_dump()
        records.append({"id": str(row.id), **cast(dict[str, object], parsed)})
    return records


def _create(  # noqa: UP047
    db: Session,
    user: User,
    record_type: type[Record],
    payload: BaseModel,
    action: str,
) -> dict[str, object]:
    count = int(
        db.scalar(
            select(func.count()).select_from(record_type).where(record_type.user_id == user.id)
        )
        or 0
    )
    if count >= 200:
        raise HTTPException(status_code=409, detail="You have reached the 200 saved-record limit")
    row = record_type(user_id=user.id, encrypted_data=_pack(payload))
    db.add(row)
    db.flush()
    db.add(AuditLog(actor_user_id=user.id, action=action, target=str(row.id)))
    db.commit()
    return {"id": str(row.id), **payload.model_dump()}


def _update(  # noqa: UP047
    db: Session,
    user: User,
    row_id: UUID,
    record_type: type[Record],
    payload: BaseModel,
    action: str,
) -> dict[str, object]:
    row = db.scalar(
        select(record_type).where(record_type.id == row_id, record_type.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Saved record not found")
    row.encrypted_data = _pack(payload)
    db.add(AuditLog(actor_user_id=user.id, action=action, target=str(row.id)))
    db.commit()
    return {"id": str(row.id), **payload.model_dump()}


def _delete(  # noqa: UP047
    db: Session,
    user: User,
    row_id: UUID,
    record_type: type[Record],
    action: str,
) -> Response:
    row = db.scalar(
        select(record_type).where(record_type.id == row_id, record_type.user_id == user.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Saved record not found")
    db.add(AuditLog(actor_user_id=user.id, action=action, target=str(row.id)))
    db.delete(row)
    db.commit()
    return Response(status_code=204)


@router.get("/clients")
def list_clients(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user, _session = _owner(db, raw_session)
    return _list_records(db, user, SavedInvoiceClient, ClientPayload)


@router.post("/clients", status_code=201, dependencies=[Depends(require_csrf)])
def create_client(
    body: ClientPayload,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _owner(db, raw_session)
    return _create(db, user, SavedInvoiceClient, body, "invoice_client.created")


@router.put("/clients/{record_id}", dependencies=[Depends(require_csrf)])
def update_client(
    record_id: UUID,
    body: ClientPayload,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _owner(db, raw_session)
    return _update(db, user, record_id, SavedInvoiceClient, body, "invoice_client.updated")


@router.delete("/clients/{record_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_client(
    record_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user, _session = _owner(db, raw_session)
    return _delete(db, user, record_id, SavedInvoiceClient, "invoice_client.deleted")


@router.get("/items")
def list_items(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user, _session = _owner(db, raw_session)
    return _list_records(db, user, SavedInvoiceItem, ItemPayload)


@router.post("/items", status_code=201, dependencies=[Depends(require_csrf)])
def create_item(
    body: ItemPayload,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _owner(db, raw_session)
    return _create(db, user, SavedInvoiceItem, body, "invoice_item.created")


@router.put("/items/{record_id}", dependencies=[Depends(require_csrf)])
def update_item(
    record_id: UUID,
    body: ItemPayload,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _owner(db, raw_session)
    return _update(db, user, record_id, SavedInvoiceItem, body, "invoice_item.updated")


@router.delete("/items/{record_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_item(
    record_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user, _session = _owner(db, raw_session)
    return _delete(db, user, record_id, SavedInvoiceItem, "invoice_item.deleted")


@router.post("/number", dependencies=[Depends(require_csrf)])
def reserve_invoice_number(
    body: NumberRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, str]:
    user, _session = _owner(db, raw_session)
    try:
        number = reserve_number(db, user.id, body.document_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Could not reserve an invoice number") from exc
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="invoice_number.reserved",
            target=number,
        )
    )
    db.commit()
    return {"number": number}


def _next_occurrence(now: datetime, interval: str) -> datetime:
    if interval == "weekly":
        return now + timedelta(days=7)
    month_index = now.month
    year = now.year + (month_index // 12)
    month = month_index % 12 + 1
    from calendar import monthrange

    return now.replace(year=year, month=month, day=min(now.day, monthrange(year, month)[1]))


@router.get("/recurring")
def list_recurring_schedules(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> list[dict[str, object]]:
    user, _session = _owner(db, raw_session)
    rows = list(
        db.scalars(
            select(RecurringInvoiceSchedule)
            .where(RecurringInvoiceSchedule.user_id == user.id)
            .order_by(RecurringInvoiceSchedule.created_at.desc())
        )
    )
    return [
        {
            "id": str(row.id),
            "interval": row.interval,
            "active": row.active,
            "next_run_at": row.next_run_at.isoformat(),
            "last_job_id": str(row.last_job_id) if row.last_job_id else None,
        }
        for row in rows
    ]


@router.post("/recurring", status_code=201, dependencies=[Depends(require_csrf)])
def create_recurring_schedule(
    body: RecurringRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user, _session = _owner(db, raw_session)
    if user_level(db, user) < Level.PRO:
        raise HTTPException(
            status_code=402,
            detail="Recurring invoices require Pro",
            headers={"X-Paywall": "pro-required"},
        )
    active_count = int(
        db.scalar(
            select(func.count())
            .select_from(RecurringInvoiceSchedule)
            .where(
                RecurringInvoiceSchedule.user_id == user.id,
                RecurringInvoiceSchedule.active.is_(True),
            )
        )
        or 0
    )
    if active_count >= 20:
        raise HTTPException(status_code=409, detail="You can have up to 20 active schedules")
    try:
        invoice = InvoicePayload.model_validate(body.invoice)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invoice details are invalid") from exc
    if invoice.document_type != "invoice":
        raise HTTPException(status_code=422, detail="Only invoices can repeat")
    now = datetime.now(UTC)
    schedule = RecurringInvoiceSchedule(
        user_id=user.id,
        interval=body.interval,
        anchor_day=now.day,
        encrypted_invoice_json=encrypt_secret(invoice.model_dump_json()),
        active=True,
        next_run_at=_next_occurrence(now, body.interval),
    )
    db.add(schedule)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="recurring_invoice.created",
            target=str(schedule.id),
        )
    )
    db.commit()
    return {
        "id": str(schedule.id),
        "interval": schedule.interval,
        "active": schedule.active,
        "next_run_at": schedule.next_run_at.isoformat(),
    }


@router.patch("/recurring/{schedule_id}", dependencies=[Depends(require_csrf)])
def update_recurring_schedule(
    schedule_id: UUID,
    body: RecurringActiveRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, bool]:
    user, _session = _owner(db, raw_session)
    row = db.scalar(
        select(RecurringInvoiceSchedule).where(
            RecurringInvoiceSchedule.id == schedule_id,
            RecurringInvoiceSchedule.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    if body.active and user_level(db, user) < Level.PRO:
        raise HTTPException(status_code=402, detail="Recurring invoices require Pro")
    row.active = body.active
    db.add(
        AuditLog(
            actor_user_id=user.id,
            action="recurring_invoice.resumed" if body.active else "recurring_invoice.paused",
            target=str(row.id),
        )
    )
    db.commit()
    return {"active": row.active}


@router.delete("/recurring/{schedule_id}", status_code=204, dependencies=[Depends(require_csrf)])
def delete_recurring_schedule(
    schedule_id: UUID,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> Response:
    user, _session = _owner(db, raw_session)
    row = db.scalar(
        select(RecurringInvoiceSchedule).where(
            RecurringInvoiceSchedule.id == schedule_id,
            RecurringInvoiceSchedule.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Recurring invoice not found")
    db.add(AuditLog(actor_user_id=user.id, action="recurring_invoice.deleted", target=str(row.id)))
    db.delete(row)
    db.commit()
    return Response(status_code=204)
