from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from rendercart.auth.models import ApiKey, AuthSession, User
from rendercart.auth.security import digest_secret
from rendercart.billing.access import user_level
from rendercart.core.access import Level
from rendercart.core.db import get_db
from rendercart.core.redis import increment_window
from rendercart.jobs.models import ToolOverride
from rendercart.jobs.router import (
    JobRequest,
    UploadRequest,
    create_job,
    create_upload,
    get_job,
    registry,
)
from rendercart.registry.models import ToolManifest

router = APIRouter(prefix="/v1", tags=["developer API"])
Db = Annotated[Session, Depends(get_db)]
T = TypeVar("T")


class PublicJobRequest(BaseModel):
    upload_ids: list[UUID] = Field(min_length=0, max_length=50)
    options: dict[str, object] = Field(default_factory=dict)
    batch_mode: bool = False


def _api_owner(
    db: Session,
    authorization: str | None,
) -> tuple[ApiKey, User]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="A RenderCart API key is required")
    raw_key = authorization[7:].strip()
    if not raw_key.startswith("rc_live_") or len(raw_key) < 40:
        raise HTTPException(status_code=401, detail="Invalid API key")
    row = db.scalar(select(ApiKey).where(ApiKey.key_hash == digest_secret(raw_key)))
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    user = db.get(User, row.user_id)
    if user is None or user.is_banned or user_level(db, user) < Level.PRO:
        raise HTTPException(status_code=403, detail="The API requires an active Pro account")
    row.last_used_at = datetime.now(UTC)
    db.commit()
    if increment_window(f"public-api:{row.id}:minute", 60) > 120:
        raise HTTPException(status_code=429, detail="API rate limit exceeded")
    return row, user


def _temporary_session(db: Session, user: User, request: Request) -> str:
    raw_token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=digest_secret(raw_token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            ip=request.client.host if request.client else None,
            user_agent="RenderCart developer API",
            mfa_verified=False,
        )
    )
    db.commit()
    return raw_token


def _remove_temporary_session(db: Session, raw_token: str) -> None:
    row = db.get(AuthSession, digest_secret(raw_token))
    if row is not None:
        db.delete(row)
        db.commit()


def _run_as_api_user(  # noqa: UP047
    db: Session, user: User, request: Request, operation: Callable[[str], T]
) -> T:
    raw_token = _temporary_session(db, user, request)
    try:
        return operation(raw_token)
    finally:
        _remove_temporary_session(db, raw_token)


def _public_tool(tool: ToolManifest) -> dict[str, object]:
    schema: dict[str, object] | None = None
    if tool.options is not None:
        fields: dict[str, object] = {}
        for name, field in tool.options.model_fields.items():
            extra = field.json_schema_extra if isinstance(field.json_schema_extra, dict) else {}
            if extra.get("internal"):
                continue
            fields[name] = {
                "title": field.title,
                "description": field.description,
                "required": field.is_required(),
                "default": None if field.is_required() else field.default,
            }
        schema = fields
    return {
        "slug": tool.slug,
        "name": tool.name,
        "category": tool.category.value,
        "summary": tool.summary,
        "runtime": tool.runtime.value,
        "accepts_files": tool.inputs.accept if tool.inputs else [],
        "min_files": tool.inputs.min_files if tool.inputs else 0,
        "options": schema,
    }


def _get_public_tool(db: Session, slug: str) -> ToolManifest:
    tool = registry.get(slug)
    if tool is None or tool.hidden or tool.restricted or tool.min_level > Level.PRO:
        raise HTTPException(status_code=404, detail="Tool not found")
    override = db.get(ToolOverride, slug)
    if override is not None and not override.enabled:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.get("/tools")
def list_tools(
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _key, _user = _api_owner(db, authorization)
    tools = []
    for tool in registry.values():
        if tool.hidden or tool.restricted or tool.min_level > Level.PRO:
            continue
        override = db.get(ToolOverride, tool.slug)
        if override is not None and not override.enabled:
            continue
        tools.append(_public_tool(tool))
    return {"tools": tools}


@router.get("/tools/{slug}")
def get_tool(
    slug: str,
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _key, _user = _api_owner(db, authorization)
    return _public_tool(_get_public_tool(db, slug))


@router.post("/uploads/presign")
def create_api_upload(
    body: UploadRequest,
    request: Request,
    response: Response,
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _key, user = _api_owner(db, authorization)
    tool = _get_public_tool(db, body.tool_slug)
    if tool.inputs is None:
        raise HTTPException(status_code=400, detail="Tool does not accept uploaded files")
    return _run_as_api_user(
        db,
        user,
        request,
        lambda raw: create_upload(body, request, response, db, raw_session=raw, raw_guest=None),
    )


@router.post("/tools/{slug}/jobs", status_code=202)
def create_api_job(
    slug: str,
    body: PublicJobRequest,
    request: Request,
    response: Response,
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _key, user = _api_owner(db, authorization)
    _get_public_tool(db, slug)
    job_request = JobRequest(
        upload_ids=body.upload_ids,
        options=body.options,
        batch_mode=body.batch_mode,
    )
    result = _run_as_api_user(
        db,
        user,
        request,
        lambda raw: create_job(
            slug,
            job_request,
            request,
            response,
            db,
            raw_session=raw,
            raw_guest=None,
        ),
    )
    result["status_url"] = f"/v1/jobs/{result['job_id']}"
    return result


@router.get("/jobs/{job_id}")
def get_api_job(
    job_id: UUID,
    request: Request,
    response: Response,
    db: Db,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _key, user = _api_owner(db, authorization)
    return _run_as_api_user(
        db,
        user,
        request,
        lambda raw: get_job(job_id, db, response, raw_session=raw, raw_guest=None),
    )
