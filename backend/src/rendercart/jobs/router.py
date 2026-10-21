import asyncio
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import PurePath
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from rendercart.ai.models import ChatDocument, ChatTurn
from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.auth.router import require_csrf
from rendercart.billing.access import user_level
from rendercart.core.access import Level
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.core.guest import decode_guest_id, encode_guest_id, new_guest_id
from rendercart.core.redis import increment_window
from rendercart.core.turnstile import verify_turnstile
from rendercart.jobs.batch import execution_timeout
from rendercart.jobs.celery_app import app as celery_app
from rendercart.jobs.models import (
    CreditAccount,
    CreditLedger,
    CreditLot,
    CreditReservation,
    Job,
    JobState,
    ToolOverride,
    Upload,
)
from rendercart.jobs.options import encrypt_sensitive_options
from rendercart.jobs.quota import redis_client, release_key, reserve_counter
from rendercart.jobs.storage import presign_download, presign_upload
from rendercart.registry.loader import load_builtin_registry
from rendercart.registry.models import Category, Limit, ToolManifest

router = APIRouter(prefix="/api", tags=["jobs"])
Db = Annotated[Session, Depends(get_db)]
registry = load_builtin_registry()
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._ -]")


class UploadRequest(BaseModel):
    tool_slug: str
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=127)
    size_bytes: int = Field(gt=0, le=2_147_483_648)


class JobRequest(BaseModel):
    upload_ids: list[UUID] = Field(min_length=0, max_length=50)
    options: dict[str, object] = Field(default_factory=dict)
    batch_mode: bool = False
    turnstile_token: str | None = Field(default=None, max_length=2048)
    paid_tier: Literal["job_s", "job_m", "job_l"] | None = None


class ChatQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)


def _subject(
    db: Session,
    raw_session: str | None,
    raw_guest: str | None,
    response: Response | None = None,
) -> tuple[User | None, str | None, Level]:
    if raw_session:
        session_pair = auth_service.get_session_user(db, raw_session)
        if session_pair:
            user, _session = session_pair
            level = user_level(db, user)
            return user, None, level
    guest_id: str | None = None
    if raw_guest:
        guest_id = decode_guest_id(raw_guest)
    if guest_id is None:
        guest_id = new_guest_id()
        if response:
            response.set_cookie(
                get_settings().guest_cookie_name,
                encode_guest_id(guest_id),
                max_age=30 * 86400,
                secure=get_settings().app_env == "production",
                httponly=True,
                samesite="lax",
                path="/",
            )
    return None, guest_id, Level.GUEST


def _subject_key(user: User | None, guest_id: str | None) -> str:
    return f"u:{user.id}" if user else f"g:{guest_id}"


def _tool_access(slug: str, level: Level, db: Session) -> ToolManifest:
    tool = registry.get(slug)
    if tool is None or tool.hidden or level < tool.min_level:
        raise HTTPException(status_code=404, detail="Tool not found")
    override = db.get(ToolOverride, slug)
    if override and not override.enabled:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


def _tool_limit(tool: ToolManifest, level: Level, db: Session) -> Limit | None:
    override = db.get(ToolOverride, tool.slug)
    if override:
        level_override = override.limits.get(level.name.lower())
        if level_override:
            return Limit.model_validate(level_override)
    fallback_level = (
        Level.PRO if level >= Level.DAY_PASS else Level.FREE if level == Level.FREE else Level.GUEST
    )
    return tool.limits.get(level) or tool.limits.get(fallback_level)


def _max_for(mapping: dict[Level, int], level: Level, default: int) -> int:
    allowed = [value for role, value in mapping.items() if role <= level]
    return max(allowed) if allowed else default


def _seconds_until_next_month(now: datetime) -> int:
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return max(1, int((next_month - now).total_seconds()) + 86_400)


def _clean_filename(name: str) -> str:
    cleaned = _SAFE_FILENAME.sub("_", PurePath(name).name).strip(" .")
    return cleaned[:180] or "upload.bin"


@router.post("/uploads/presign", dependencies=[Depends(require_csrf)])
def create_upload(
    body: UploadRequest,
    request: Request,
    response: Response,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> dict[str, object]:
    user, guest_id, level = _subject(db, raw_session, raw_guest, response)
    ip = request.client.host if request.client else "unknown"
    if increment_window(f"upload:presign:ip:{ip}", 3600) > 30:
        raise HTTPException(status_code=429, detail="Too many upload requests. Try again later.")
    tool = _tool_access(body.tool_slug, level, db)
    if tool.inputs is None:
        raise HTTPException(status_code=400, detail="Tool does not accept uploaded files")
    if body.content_type not in tool.inputs.accept:
        raise HTTPException(status_code=415, detail="File type is not supported")
    configured_limit = _tool_limit(tool, level, db)
    max_mb = (configured_limit.max_total_mb if configured_limit else None) or _max_for(
        tool.inputs.max_total_mb, level, 10
    )
    if body.size_bytes > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds your plan's size limit")
    name = _clean_filename(body.filename)
    upload_id = uuid4()
    owner = _subject_key(user, guest_id)
    key = f"{owner}/{upload_id}/{name}"
    upload = Upload(
        id=upload_id,
        user_id=user.id if user else None,
        guest_id=guest_id,
        object_key=key,
        filename=name,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db.add(upload)
    db.commit()
    return {
        "upload_id": str(upload_id),
        "upload_url": presign_upload(key, body.content_type),
        "method": "PUT",
        "headers": {"Content-Type": body.content_type},
        "expires_in": get_settings().upload_url_ttl_seconds,
    }


@router.post("/tools/{slug}/jobs", status_code=202, dependencies=[Depends(require_csrf)])
def create_job(
    slug: str,
    body: JobRequest,
    request: Request,
    response: Response,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> dict[str, object]:
    user, guest_id, level = _subject(db, raw_session, raw_guest, response)
    if body.paid_tier and user is None:
        raise HTTPException(status_code=401, detail="Sign in before purchasing a single job")
    if user is None:
        ip = request.client.host if request.client else "unknown"
        if not verify_turnstile(body.turnstile_token, ip):
            raise HTTPException(
                status_code=403, detail="Complete the anti-bot check before starting a job"
            )
        if increment_window(f"jobs:guest:ip:{ip}", 3600) > 20:
            raise HTTPException(
                status_code=429, detail="Too many jobs from this network. Try again later."
            )
    paid_tier = body.paid_tier
    if paid_tier:
        tool = registry.get(slug)
        if tool is None or tool.hidden or tool.min_level > Level.PRO:
            raise HTTPException(status_code=404, detail="Tool not found")
        required_tier = f"job_{tool.job_tier.value.lower()}" if tool.job_tier else None
        if paid_tier != required_tier:
            raise HTTPException(
                status_code=400, detail="Single-job price tier does not match this tool"
            )
        limit_level = Level.PRO
    else:
        tool = _tool_access(slug, level, db)
        limit_level = level
    if body.batch_mode:
        if paid_tier:
            raise HTTPException(status_code=400, detail="Batch jobs require an active Pro plan")
        if level < Level.PRO:
            raise HTTPException(
                status_code=402,
                detail="Batch processing is available with Pro",
                headers={"X-Paywall": "pro-required"},
            )
        if not tool.batchable or tool.category != Category.PDF:
            raise HTTPException(status_code=400, detail="This tool does not support batch jobs")
        if len(body.upload_ids) < 2:
            raise HTTPException(status_code=422, detail="Batch mode needs at least two files")
        if len(body.upload_ids) > tool.batch_max_files:
            raise HTTPException(
                status_code=413,
                detail=f"Batch jobs accept at most {tool.batch_max_files} files",
            )
        if tool.slug == "merge-pdf" and len(body.upload_ids) % 2:
            raise HTTPException(
                status_code=422,
                detail="Batch Merge PDF needs an even number of files, paired in selection order",
            )
    if tool.inputs is None:
        raise HTTPException(status_code=400, detail="Tool does not accept uploaded files")
    if len(set(body.upload_ids)) != len(body.upload_ids):
        raise HTTPException(status_code=400, detail="Duplicate uploads are not allowed")
    if len(body.upload_ids) < tool.inputs.min_files:
        raise HTTPException(
            status_code=422, detail=f"At least {tool.inputs.min_files} files are required"
        )
    uploads_by_id = {
        upload.id: upload
        for upload in db.scalars(select(Upload).where(Upload.id.in_(body.upload_ids)))
    }
    uploads = [
        uploads_by_id[upload_id] for upload_id in body.upload_ids if upload_id in uploads_by_id
    ]
    if len(uploads) != len(set(body.upload_ids)):
        raise HTTPException(status_code=400, detail="One or more uploads are invalid")
    if any(
        (upload.user_id != user.id if user else upload.guest_id != guest_id)
        or upload.expires_at <= datetime.now(UTC)
        or upload.content_type not in tool.inputs.accept
        for upload in uploads
    ):
        raise HTTPException(status_code=404, detail="Upload not found")
    configured_limit = _tool_limit(tool, limit_level, db)
    max_files = (configured_limit.max_files if configured_limit else None) or _max_for(
        tool.inputs.max_files, limit_level, 1
    )
    if body.batch_mode:
        override = db.get(ToolOverride, tool.slug)
        level_override = override.limits.get(limit_level.name.lower()) if override else None
        configured_batch_max = (
            Limit.model_validate(level_override).max_files if level_override else None
        )
        max_files = min(configured_batch_max or tool.batch_max_files, tool.batch_max_files)
    max_mb = (configured_limit.max_total_mb if configured_limit else None) or _max_for(
        tool.inputs.max_total_mb, limit_level, 10
    )
    if len(uploads) > max_files or sum(item.size_bytes for item in uploads) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Upload exceeds your plan's limits")
    if slug == "chat-with-pdf" and level < Level.DAY_PASS:
        now = datetime.now(UTC)
        active_document_filter = (
            ChatDocument.user_id == user.id if user else ChatDocument.guest_id == guest_id
        )
        active_document = db.scalar(
            select(ChatDocument.id).where(
                active_document_filter,
                or_(ChatDocument.expires_at.is_(None), ChatDocument.expires_at > now),
            )
        )
        if active_document:
            raise HTTPException(
                status_code=409,
                detail="Delete your current document chat before indexing another PDF",
            )
    limit = _tool_limit(tool, limit_level, db)
    options: dict[str, object] = body.options
    options.pop("batch_mode", None)
    if tool.options:
        try:
            parsed_options = tool.options.model_validate(options)
            options = parsed_options.model_dump(mode="json")
            if (
                slug == "resume-builder"
                and options.get("template") != "classic"
                and level < Level.DAY_PASS
                and paid_tier is None
            ):
                raise HTTPException(
                    status_code=402,
                    detail="Modern and compact resume layouts are available with a day pass or Pro",
                    headers={"X-Paywall": "pro-required"},
                )
            if slug == "resume-builder" and options.get("rewrite_with_ai") and level < Level.PRO:
                raise HTTPException(
                    status_code=402,
                    detail="AI resume rewriting is available with Pro",
                    headers={"X-Paywall": "pro-required"},
                )
            if limit and limit.max_pages and "max_pages" in tool.options.model_fields:
                options["max_pages"] = limit.max_pages
            if "bill_credits" in tool.options.model_fields:
                options["bill_credits"] = (
                    Level.DAY_PASS <= level < Level.ADMIN and paid_tier is None
                )
            if "branded" in tool.options.model_fields:
                options["branded"] = level < Level.DAY_PASS and paid_tier is None
            if "max_minutes_per_month" in tool.options.model_fields:
                options["max_minutes_per_month"] = (
                    limit.max_minutes_per_month
                    if limit and level < Level.DAY_PASS and paid_tier is None
                    else None
                )
            if "max_characters" in tool.options.model_fields:
                options["max_characters"] = limit.max_characters_per_job if limit else None
            if "max_words" in tool.options.model_fields:
                options["max_words"] = limit.max_words_per_job if limit else None
            if "word_count_per_day" in tool.options.model_fields:
                options["word_count_per_day"] = (
                    limit.word_count_per_day
                    if limit and level < Level.DAY_PASS and paid_tier is None
                    else None
                )
            if "signer_ip" in tool.options.model_fields:
                options["signer_ip"] = request.client.host if request.client else "unknown"
            if "signed_at" in tool.options.model_fields:
                options["signed_at"] = datetime.now(UTC).isoformat()
            if "consented" in tool.options.model_fields and not options.get("consented"):
                raise HTTPException(status_code=422, detail="Signing consent is required")
            options = encrypt_sensitive_options(tool, options)
            if tool.preview_then_pay and "preview" in tool.options.model_fields:
                options["preview"] = level < Level.DAY_PASS and paid_tier is None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid tool options") from exc
    options["batch_mode"] = body.batch_mode
    quota_key: str | None = None
    if not paid_tier and limit and limit.count_per_day is not None:
        quota_key = (
            f"quota:daily:{datetime.now(UTC).date().isoformat()}:"
            f"{_subject_key(user, guest_id)}:{slug}"
        )
        if not reserve_counter(quota_key, limit.count_per_day, 172800):
            raise HTTPException(
                status_code=402,
                detail="Daily free limit reached",
                headers={"X-Paywall": "daily-limit"},
            )
    elif not paid_tier and limit and limit.fair_use_per_hour is not None:
        current_hour = datetime.now(UTC).strftime("%Y-%m-%dT%H")
        quota_key = f"quota:hourly:{current_hour}:{_subject_key(user, guest_id)}:{slug}"
        if not reserve_counter(quota_key, limit.fair_use_per_hour, 7200):
            raise HTTPException(status_code=429, detail="Hourly fair-use limit reached")
    elif not paid_tier and limit and limit.count_per_month is not None:
        now = datetime.now(UTC)
        quota_key = f"quota:monthly:{now:%Y-%m}:{_subject_key(user, guest_id)}:{slug}"
        if not reserve_counter(quota_key, limit.count_per_month, _seconds_until_next_month(now)):
            raise HTTPException(
                status_code=402,
                detail="Monthly free limit reached",
                headers={"X-Paywall": "monthly-limit"},
            )
    job_id = uuid4()
    cost = (
        0
        if (
            paid_tier
            or level < Level.DAY_PASS
            or level >= Level.ADMIN
            or tool.credit_cost_per_10_pages
        )
        else ((tool.credit_cost or 0) * (len(uploads) if body.batch_mode else 1))
    )
    if (
        slug == "resume-builder"
        and options.get("rewrite_with_ai")
        and level < Level.ADMIN
        and paid_tier is None
    ):
        cost += 2
    try:
        if cost and user:
            account = db.get(CreditAccount, user.id, with_for_update=True)
            if account is None or account.balance - account.held < cost:
                raise HTTPException(
                    status_code=402, detail="Not enough credits", headers={"X-Paywall": "credits"}
                )
            lots = list(
                db.scalars(
                    select(CreditLot)
                    .where(
                        CreditLot.user_id == user.id,
                        CreditLot.remaining > CreditLot.held,
                        or_(
                            CreditLot.expires_at.is_(None), CreditLot.expires_at > datetime.now(UTC)
                        ),
                    )
                    .order_by(CreditLot.expires_at.asc().nulls_last(), CreditLot.created_at.asc())
                    .with_for_update()
                )
            )
            remaining_cost = cost
            for lot in lots:
                allocated = min(remaining_cost, lot.remaining - lot.held)
                if allocated <= 0:
                    continue
                lot.held += allocated
                db.add(CreditReservation(job_id=job_id, credit_lot_id=lot.id, amount=allocated))
                remaining_cost -= allocated
                if remaining_cost == 0:
                    break
            if remaining_cost:
                raise HTTPException(
                    status_code=402,
                    detail="Not enough unexpired credits",
                    headers={"X-Paywall": "credits"},
                )
            account.held += cost
            db.add(CreditLedger(user_id=user.id, job_id=job_id, amount=0, kind="hold"))
        elif cost:
            raise HTTPException(
                status_code=402, detail="Sign in to use credits", headers={"X-Paywall": "sign-in"}
            )
        now = datetime.now(UTC)
        job = Job(
            id=job_id,
            user_id=user.id if user else None,
            guest_id=guest_id,
            tool_slug=slug,
            payment_tier=paid_tier,
            charged_credits=cost,
            state=JobState.AWAITING_PAYMENT if paid_tier else JobState.QUEUED,
            options=options,
            input_upload_ids=[str(item.id) for item in uploads],
            quota_reserved=quota_key is not None,
            quota_key=quota_key,
            expires_at=now + (timedelta(hours=24) if paid_tier else timedelta(days=1)),
        )
        if paid_tier:
            for upload in uploads:
                upload.expires_at = max(upload.expires_at, now + timedelta(hours=24))
        db.add(job)
        db.commit()
    except Exception:
        db.rollback()
        if quota_key:
            release_key(quota_key)
        raise
    if paid_tier:
        return {
            "job_id": str(job_id),
            "state": job.state.value,
            "status_url": f"/api/jobs/{job_id}",
            "payment_product": paid_tier,
        }
    try:
        timeout_s = execution_timeout(tool, len(uploads), batch_mode=body.batch_mode)
        queue_name = tool.queue.value if tool.queue else "cpu.default"
        if slug == "chat-with-pdf" and get_settings().ai_mode == "mock":
            queue_name = "cpu.heavy"
        celery_app.send_task(
            "rendercart.jobs.tasks.execute_tool",
            args=[str(job_id)],
            queue=queue_name,
            time_limit=timeout_s,
            soft_time_limit=max(1, timeout_s - 15),
        )
    except Exception as exc:
        if cost and user:
            account = db.get(CreditAccount, user.id, with_for_update=True)
            reservations = list(
                db.scalars(select(CreditReservation).where(CreditReservation.job_id == job_id))
            )
            for reservation in reservations:
                held_lot = db.get(CreditLot, reservation.credit_lot_id, with_for_update=True)
                if held_lot:
                    held_lot.held = max(0, held_lot.held - reservation.amount)
                db.delete(reservation)
            if account:
                account.held = max(0, account.held - cost)
                db.add(CreditLedger(user_id=user.id, job_id=job_id, amount=0, kind="release"))
        job.state = JobState.FAILED
        job.error_code = "queue_unavailable"
        job.finished_at = datetime.now(UTC)
        db.commit()
        if job.quota_reserved and job.quota_key:
            release_key(job.quota_key)
        raise HTTPException(status_code=503, detail="Job queue is temporarily unavailable") from exc
    return {"job_id": str(job_id), "state": job.state.value, "status_url": f"/api/jobs/{job_id}"}


@router.get("/chat/documents")
def list_chat_documents(
    db: Db,
    response: Response,
    limit: int = 50,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> list[dict[str, object]]:
    user, guest_id, _level = _subject(db, raw_session, raw_guest, response)
    now = datetime.now(UTC)
    statement = (
        select(ChatDocument).order_by(ChatDocument.created_at.desc()).limit(max(1, min(limit, 100)))
    )
    statement = (
        statement.where(ChatDocument.user_id == user.id)
        if user
        else statement.where(ChatDocument.guest_id == guest_id)
    )
    documents = list(db.scalars(statement))
    result: list[dict[str, object]] = []
    for document in documents:
        if document.expires_at and document.expires_at <= now:
            continue
        turns = list(
            db.scalars(
                select(ChatTurn)
                .where(ChatTurn.document_id == document.id)
                .order_by(ChatTurn.created_at.asc())
            )
        )
        result.append(
            {
                "document_id": str(document.id),
                "indexed_job_id": (
                    str(document.indexed_job_id) if document.indexed_job_id else None
                ),
                "filename": document.filename,
                "page_count": document.page_count,
                "created_at": document.created_at.isoformat() if document.created_at else None,
                "expires_at": document.expires_at.isoformat() if document.expires_at else None,
                "turns": [
                    {
                        "turn_id": str(turn.id),
                        "job_id": str(turn.job_id) if turn.job_id else None,
                        "question": turn.question,
                        "answer": turn.answer,
                        "citations": turn.citations,
                        "status": turn.status,
                        "error_code": turn.error_code,
                        "created_at": turn.created_at.isoformat() if turn.created_at else None,
                    }
                    for turn in turns
                ],
            }
        )
    return result


@router.delete(
    "/chat/documents/{document_id}",
    status_code=204,
    dependencies=[Depends(require_csrf)],
)
def delete_chat_document(
    document_id: UUID,
    db: Db,
    response: Response,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> Response:
    user, guest_id, _level = _subject(db, raw_session, raw_guest, response)
    owner_filter = ChatDocument.user_id == user.id if user else ChatDocument.guest_id == guest_id
    document = db.scalar(select(ChatDocument).where(ChatDocument.id == document_id, owner_filter))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(document)
    db.commit()
    return Response(status_code=204)


@router.post(
    "/chat/documents/{document_id}/questions",
    status_code=202,
    dependencies=[Depends(require_csrf)],
)
def create_chat_question(
    document_id: UUID,
    body: ChatQuestionRequest,
    request: Request,
    response: Response,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> dict[str, object]:
    from rendercart.jobs.tasks import _fail_job

    user, guest_id, level = _subject(db, raw_session, raw_guest, response)
    ip = request.client.host if request.client else "unknown"
    if increment_window(f"chat:question:ip:{ip}", 3600) > 30:
        raise HTTPException(status_code=429, detail="Too many questions. Try again later.")
    owner_filter = ChatDocument.user_id == user.id if user else ChatDocument.guest_id == guest_id
    document = db.scalar(select(ChatDocument).where(ChatDocument.id == document_id, owner_filter))
    now = datetime.now(UTC)
    if document is None or (document.expires_at and document.expires_at <= now):
        raise HTTPException(status_code=404, detail="Document not found")
    if document.indexed_job_id:
        index_job = db.get(Job, document.indexed_job_id)
        if index_job and index_job.state != JobState.SUCCEEDED:
            raise HTTPException(status_code=409, detail="Document indexing is not complete")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question cannot be empty")

    quota_key: str | None = None
    if level < Level.DAY_PASS:
        subject = _subject_key(user, guest_id)
        quota_key = f"quota:chat-questions:{now:%Y-%m-%d}:{subject}"
        if not reserve_counter(quota_key, 10, 172_800):
            raise HTTPException(
                status_code=402,
                detail="Daily question limit reached",
                headers={"X-Paywall": "daily-limit"},
            )

    job_id = uuid4()
    turn_id = uuid4()
    job = Job(
        id=job_id,
        user_id=user.id if user else None,
        guest_id=guest_id,
        tool_slug="chat-with-pdf",
        charged_credits=0,
        state=JobState.QUEUED,
        options={"document_id": str(document.id), "turn_id": str(turn_id)},
        input_upload_ids=[],
        quota_reserved=quota_key is not None,
        quota_key=quota_key,
        expires_at=now + timedelta(hours=2),
    )
    try:
        db.add(job)
        db.flush()
        if Level.DAY_PASS <= level < Level.ADMIN:
            if user is None:
                raise HTTPException(status_code=401, detail="Sign in to use credits")
            account = db.get(CreditAccount, user.id, with_for_update=True)
            if account is None or account.balance - account.held < 1:
                raise HTTPException(
                    status_code=402,
                    detail="Not enough credits",
                    headers={"X-Paywall": "credits"},
                )
            lots = list(
                db.scalars(
                    select(CreditLot)
                    .where(
                        CreditLot.user_id == user.id,
                        CreditLot.remaining > CreditLot.held,
                        or_(CreditLot.expires_at.is_(None), CreditLot.expires_at > now),
                    )
                    .order_by(CreditLot.expires_at.asc().nulls_last(), CreditLot.created_at.asc())
                    .with_for_update()
                )
            )
            lot = next((item for item in lots if item.remaining - item.held > 0), None)
            if lot is None:
                raise HTTPException(
                    status_code=402,
                    detail="Not enough unexpired credits",
                    headers={"X-Paywall": "credits"},
                )
            lot.held += 1
            account.held += 1
            job.charged_credits = 1
            db.add(CreditReservation(job_id=job_id, credit_lot_id=lot.id, amount=1))
            db.add(CreditLedger(user_id=user.id, job_id=job_id, amount=0, kind="hold"))
        db.add(
            ChatTurn(
                id=turn_id,
                document_id=document.id,
                job_id=job_id,
                question=question,
                status="queued",
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        if quota_key:
            release_key(quota_key)
        raise

    try:
        celery_app.send_task(
            "rendercart.jobs.tasks.answer_chat_question",
            args=[str(job_id)],
            queue="cpu.heavy",
            time_limit=300,
            soft_time_limit=270,
        )
    except Exception as exc:
        _fail_job(db, job, "queue_unavailable")
        turn = db.get(ChatTurn, turn_id)
        if turn:
            turn.status = "failed"
            turn.error_code = "queue_unavailable"
            turn.completed_at = datetime.now(UTC)
            db.commit()
        raise HTTPException(status_code=503, detail="Question queue is unavailable") from exc
    return {"turn_id": str(turn_id), "job_id": str(job_id), "state": "queued"}


@router.get("/security/config")
def security_config() -> dict[str, str | None]:
    return {"turnstile_site_key": get_settings().turnstile_site_key}


def _get_owned_job(db: Session, job_id: UUID, user: User | None, guest_id: str | None) -> Job:
    job = db.get(Job, job_id)
    if job is None or (job.user_id != user.id if user else job.guest_id != guest_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}")
def get_job(
    job_id: UUID,
    db: Db,
    response: Response,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> dict[str, object]:
    user, guest_id, _level = _subject(db, raw_session, raw_guest, response)
    job = _get_owned_job(db, job_id, user, guest_id)
    result: dict[str, object] = {
        "job_id": str(job.id),
        "tool_slug": job.tool_slug,
        "state": job.state.value,
        "progress": job.progress,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "error_code": job.error_code,
    }
    if (
        job.state == JobState.SUCCEEDED
        and job.output_key
        and job.output_filename
        and job.tool_slug != "chat-with-pdf"
    ):
        result["download_url"] = presign_download(job.output_key, job.output_filename)
    if job.state == JobState.SUCCEEDED and job.locked_output_key:
        result["locked_preview"] = True
        tool = registry.get(job.tool_slug)
        if user is not None and tool and tool.job_tier:
            result["can_unlock"] = True
            result["payment_product"] = f"job_{tool.job_tier.value.lower()}"
        else:
            result["can_unlock"] = False
    return result


@router.get("/jobs")
def list_jobs(
    db: Db,
    response: Response,
    limit: int = 30,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> list[dict[str, object]]:
    user, guest_id, _level = _subject(db, raw_session, raw_guest, response)
    statement = select(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 100)))
    statement = (
        statement.where(Job.user_id == user.id)
        if user
        else statement.where(Job.guest_id == guest_id)
    )
    jobs = list(db.scalars(statement))
    return [
        {
            "job_id": str(job.id),
            "tool_slug": job.tool_slug,
            "state": job.state.value,
            "progress": job.progress,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "download_url": (
                presign_download(job.output_key, job.output_filename)
                if (
                    job.state == JobState.SUCCEEDED
                    and job.output_key
                    and job.output_filename
                    and job.tool_slug != "chat-with-pdf"
                )
                else None
            ),
        }
        for job in jobs
    ]


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> StreamingResponse:
    user, guest_id, _level = _subject(db, raw_session, raw_guest)
    _get_owned_job(db, job_id, user, guest_id)

    async def stream() -> AsyncIterator[str]:
        pubsub = redis_client.pubsub()  # type: ignore[no-untyped-call]
        channel = f"job:{job_id}:events"
        pubsub.subscribe(channel)
        try:
            current = _get_owned_job(db, job_id, user, guest_id)
            snapshot = json.dumps(
                {
                    "job_id": str(current.id),
                    "state": current.state.value,
                    "progress": current.progress,
                    "error_code": current.error_code,
                }
            )
            yield f"event: progress\ndata: {snapshot}\n\n"
            if current.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
                return
            while not await request.is_disconnected():
                message = await asyncio.to_thread(
                    pubsub.get_message, ignore_subscribe_messages=True, timeout=1
                )
                if message and message.get("data"):
                    yield f"event: progress\ndata: {message['data']}\n\n"
                    event_data = json.loads(message["data"])
                    if event_data.get("state") in {"succeeded", "failed", "cancelled"}:
                        break
        finally:
            pubsub.unsubscribe(channel)
            pubsub.close()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
