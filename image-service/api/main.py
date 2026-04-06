from config import settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from logging_config import generate_correlation_id, log_event, set_correlation_id

from api.app_state import logger, usage_tracker
from api.db import init_db
from api.routers.assets import router as assets_router
from api.routers.brand_kits import router as brand_kits_router
from api.routers.generation import router as generation_router
from api.routers.operations import router as operations_router
from api.routers.v1 import router as v1_router
from api.usage import normalize_usage_endpoint

app = FastAPI(
    title="RenderCart API",
    description="Product Context Image Generation Engine for RenderCart and Stockman integration.",
    version="1.0.0",
)


def _include_router_with_aliases(router) -> None:
    app.include_router(router)
    app.include_router(router, prefix="/api", include_in_schema=False)


for api_router in (operations_router, generation_router, brand_kits_router, assets_router, v1_router):
    _include_router_with_aliases(api_router)


if settings.cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.on_event("startup")
def startup_event():
    logger.info("Starting RenderCart API", extra={"environment": settings.environment})
    init_db()
    logger.info(
        "PostgreSQL startup check passed",
        extra={"postgres_host": settings.postgres_host, "postgres_db": settings.postgres_db},
    )


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or generate_correlation_id()
    set_correlation_id(correlation_id)
    request.state.correlation_id = correlation_id

    log_event(
        logger,
        event_type="request",
        job_id=None,
        status="started",
        message=f"{request.method} {request.url.path}",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method,
    )

    response = await call_next(request)

    business_id = getattr(request.state, "business_id", None)
    if business_id:
        try:
            usage_tracker.track_request(
                business_id,
                normalize_usage_endpoint(request.url.path),
                success=response.status_code < 400,
            )
        except Exception:
            logger.warning("Failed to track request usage", exc_info=True)

    log_event(
        logger,
        event_type="response",
        job_id=None,
        status="completed",
        message=f"{request.method} {request.url.path} - {response.status_code}",
        correlation_id=correlation_id,
        status_code=response.status_code,
    )
    return response
