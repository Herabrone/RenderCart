from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import sentry_sdk
import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.utils import get_openapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from rendercart.admin.router import router as admin_router
from rendercart.auth.api_keys import router as api_keys_router
from rendercart.auth.router import router as auth_router
from rendercart.billing.router import router as billing_router
from rendercart.business.currency_rates import router as currency_rates_router
from rendercart.business.domain_alerts import router as domain_alerts_router
from rendercart.business.dynamic_qr import public_router as dynamic_qr_public_router
from rendercart.business.dynamic_qr import router as dynamic_qr_router
from rendercart.business.invoice import router as invoice_business_router
from rendercart.business.monitors import router as monitors_router
from rendercart.business.vault import public_router as vault_public_router
from rendercart.business.vault import router as vault_router
from rendercart.business.webhook_bins import receiver_router as webhook_bin_receiver_router
from rendercart.business.webhook_bins import router as webhook_bins_router
from rendercart.business.website_audits import router as website_audits_router
from rendercart.core.access import effective_level
from rendercart.core.config import get_settings
from rendercart.core.db import get_db
from rendercart.core.logging import configure_logging
from rendercart.developer.public_api import router as public_api_router
from rendercart.jobs.models import ToolOverride
from rendercart.jobs.router import router as jobs_router
from rendercart.registry.loader import load_builtin_registry, visible_tools

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("application_started", environment=settings.app_env)
    yield
    logger.info("application_stopped")


app = FastAPI(
    title="RenderCart API",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(api_keys_router)
app.include_router(billing_router)
app.include_router(dynamic_qr_router)
app.include_router(domain_alerts_router)
app.include_router(currency_rates_router)
app.include_router(webhook_bins_router)
app.include_router(webhook_bin_receiver_router)
app.include_router(vault_router)
app.include_router(vault_public_router)
app.include_router(invoice_business_router)
app.include_router(monitors_router)
app.include_router(website_audits_router)
app.include_router(public_api_router)


@app.get("/v1/openapi.json", include_in_schema=False)
def public_openapi() -> dict[str, object]:
    return get_openapi(
        title="RenderCart Public API",
        version="v1",
        routes=public_api_router.routes,
    )


app.include_router(dynamic_qr_public_router)
app.include_router(jobs_router)
registry = load_builtin_registry()


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@app.get("/api/tools", tags=["tools"])
async def list_tools(db: Annotated[Session, Depends(get_db)]) -> list[dict[str, object]]:
    disabled = set(db.scalars(select(ToolOverride.slug).where(ToolOverride.enabled.is_(False))))
    return [
        tool.public_dict()
        for tool in visible_tools(registry, effective_level(None))
        if tool.slug not in disabled
    ]


@app.get("/api/tools/{slug}", tags=["tools"])
async def get_tool(slug: str, db: Annotated[Session, Depends(get_db)]) -> dict[str, object]:
    tool = registry.get(slug)
    override = db.get(ToolOverride, slug)
    if (
        tool is None
        or tool.hidden
        or effective_level(None) < tool.min_level
        or (override and not override.enabled)
    ):
        raise HTTPException(status_code=404, detail="Tool not found")
    detail = tool.detail_dict()
    if override:
        limits = detail["limits"]
        if isinstance(limits, dict):
            limits.update(override.limits)
        detail["prices"] = override.prices
    return detail
