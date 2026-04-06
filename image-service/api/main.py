from datetime import datetime
from typing import Generator, List, Optional

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from celery.result import AsyncResult
from kombu import Queue
import os
import time
import random
import uuid
from dotenv import load_dotenv
import redis
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import settings
from db import init_db
from models import (
    BatchGenerateRequest,
    BatchResponse,
    GenerateRequest,
    JobResponse,
    JobStatus,
    RedisJobStore,
)
from auth import APIKeyAuth
from storage import R2Storage
from usage import UsageTracker
from logging_config import setup_logging, generate_correlation_id, set_correlation_id, log_event
from business_presets import list_output_formats, list_presets
from api.db import SessionLocal
from api.models_db import BatchJob, Job, Asset

load_dotenv()

# Setup structured logging
logger = setup_logging()

api_auth = APIKeyAuth()

app = FastAPI(
    title="RenderCart API",
    description="Product Context Image Generation Engine for RenderCart and Stockman integration.",
    version="1.0.0"
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API v1 Router for Stockman integration
from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1", tags=["v1"])

@v1_router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def v1_generate(
    request: GenerateRequest,
    http_request: Request,
    business_id: str = Depends(APIKeyAuth().verify_api_key),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Generate images via API v1 with optional webhook callback."""
    job_id = f"job_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"

    log_event(
        logger,
        event_type="queued",
        job_id=job_id,
        status="pending",
        message="Job queued for processing",
        business_id=business_id,
        image_url=request.image_url,
        prompt=request.prompt,
        preset_id=request.preset_id,
        use_case=request.use_case.value,
        product_category=request.product_category.value,
        brand_style=request.brand_style,
        output_format=request.output_format.value,
        mode=request.mode.value,
        num_outputs=request.num_outputs,
    )

    redis_store.create_job(job_id, business_id, request)
    try:
        create_job_record(db, job_id, business_id, request)
    except Exception:
        logger.warning("Could not persist job record to database", exc_info=True)

    celery.send_task(
        "worker.process_job",
        args=[job_id, request.image_url, request.prompt, business_id, request.num_outputs],
        kwargs={
            "preset_id": request.preset_id,
            "use_case": request.use_case.value,
            "product_category": request.product_category.value,
            "brand_style": request.brand_style,
            "output_format": request.output_format.value,
            "mode": request.mode.value,
            "callback_url": request.callback_url,
            "metadata": request.metadata or {},
            "correlation_id": getattr(http_request.state, "correlation_id", None),
        },
        queue="generate",
    )

    created_job = redis_store.get_job(job_id)
    if created_job is None:
        raise HTTPException(status_code=500, detail="Failed to create job record")
    return created_job

@v1_router.get("/job/{job_id}")
async def v1_get_job(
    job_id: str,
    business_id: str = Depends(APIKeyAuth().verify_api_key)
) -> JobResponse:
    """Get status of a specific generation job."""
    job = redis_store.get_job(job_id)
    if not job or not job_id.startswith(f"job_{business_id}_"):
        raise HTTPException(status_code=404, detail="Job not found")
    return job

app.include_router(v1_router)


def asset_to_dict(asset: Asset) -> dict:
    return {
        "id": asset.id,
        "job_id": asset.job.job_id if asset.job else asset.job_id,
        "asset_type": asset.asset_type,
        "label": asset.label,
        "asset_url": asset.asset_url,
        "output_index": asset.output_index,
        "width": asset.width,
        "height": asset.height,
        "file_format": asset.file_format,
        "is_deleted": asset.is_deleted,
        "asset_metadata": asset.asset_metadata,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
    }


def job_to_dict(job: Job, assets: Optional[List[Asset]] = None) -> dict:
    result = {
        "job_id": job.job_id,
        "status": job.status,
        "batch_id": job.batch_id,
        "item_index": job.item_index,
        "item_label": job.item_label,
        "input_file_name": job.input_file_name,
        "original_image_url": job.original_image_url,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "image_url": job.image_url,
        "prompt": job.prompt,
        "preset_id": job.preset_id,
        "use_case": job.use_case,
        "product_category": job.product_category,
        "brand_style": job.brand_style,
        "output_format": job.output_format,
        "mode": job.mode,
        "num_outputs": job.num_outputs,
        "callback_url": job.callback_url,
        "metadata": job.job_metadata,
        "actual_model": job.actual_model,
        "inference_config_used": job.inference_config_used,
        "progress": job.progress,
        "step": job.step,
        "error": job.error,
    }
    if assets is not None:
        result["assets"] = [asset_to_dict(asset) for asset in assets]
    return result


def create_job_record(
    db: Session,
    job_id: str,
    business_id: str,
    request: GenerateRequest,
    batch_id: Optional[str] = None,
    item_index: Optional[int] = None,
    item_label: Optional[str] = None,
    input_file_name: Optional[str] = None,
    original_image_url: Optional[str] = None,
) -> Job:
    job = Job(
        job_id=job_id,
        business_id=business_id,
        batch_id=batch_id,
        item_index=item_index,
        item_label=item_label,
        input_file_name=input_file_name,
        original_image_url=original_image_url,
        status=JobStatus.PENDING.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        image_url=request.image_url,
        prompt=request.prompt,
        preset_id=request.preset_id,
        use_case=request.use_case.value,
        product_category=request.product_category.value,
        brand_style=request.brand_style,
        output_format=request.output_format.value,
        mode=request.mode.value,
        num_outputs=request.num_outputs,
        callback_url=request.callback_url,
        job_metadata=request.metadata or {},
        progress=0,
        step="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_batch_record(db: Session, batch_id: str, business_id: str, request: BatchGenerateRequest) -> BatchJob:
    batch = BatchJob(
        batch_id=batch_id,
        business_id=business_id,
        status=JobStatus.PENDING.value,
        total_items=len(request.items),
        completed_items=0,
        failed_items=0,
        pending_items=len(request.items),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata=request.metadata or {},
        prompt=request.prompt,
        preset_id=request.preset_id,
        use_case=request.use_case.value,
        product_category=request.product_category.value,
        brand_style=request.brand_style,
        output_format=request.output_format.value,
        mode=request.mode.value,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def compute_batch_status(jobs: List[Job]) -> str:
    statuses = {job.status for job in jobs}
    if all(status == JobStatus.COMPLETED.value for status in statuses) and jobs:
        return JobStatus.COMPLETED.value
    if any(status in {JobStatus.PENDING.value, JobStatus.PROCESSING.value} for status in statuses):
        return JobStatus.PROCESSING.value
    if any(status == JobStatus.FAILED.value for status in statuses):
        return JobStatus.FAILED.value
    return JobStatus.PENDING.value


def build_batch_response(batch: BatchJob, jobs: List[Job]) -> dict:
    completed_items = sum(1 for job in jobs if job.status == JobStatus.COMPLETED.value)
    failed_items = sum(1 for job in jobs if job.status == JobStatus.FAILED.value)
    pending_items = sum(1 for job in jobs if job.status == JobStatus.PENDING.value)
    total_items = len(jobs)
    progress = round(sum(job.progress or 0 for job in jobs) / total_items) if total_items else 0

    items = []
    for job in sorted(jobs, key=lambda job: (job.item_index if job.item_index is not None else 0, job.created_at)):
        items.append({
            "item_index": job.item_index,
            "label": job.item_label,
            "job_id": job.job_id,
            "status": job.status,
            "progress": job.progress or 0,
            "error": job.error,
            "output_urls": [asset.asset_url for asset in job.assets if not asset.is_deleted],
        })

    return {
        "batch_id": batch.batch_id,
        "business_id": batch.business_id,
        "status": compute_batch_status(jobs),
        "total_items": total_items,
        "completed_items": completed_items,
        "failed_items": failed_items,
        "pending_items": pending_items,
        "progress": progress,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": datetime.utcnow().isoformat(),
        "items": items,
    }


@app.get("/jobs")
@app.get("/api/jobs")
def list_jobs(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    search: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    status: Optional[JobStatus] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Job).filter(Job.business_id == business_id)

    if preset_id:
        query = query.filter(Job.preset_id == preset_id)
    if output_format:
        query = query.filter(Job.output_format == output_format)
    if status:
        query = query.filter(Job.status == status.value)
    if search:
        search_value = f"%{search}%"
        query = query.filter(
            or_(
                Job.prompt.ilike(search_value),
                Job.product_category.ilike(search_value),
                Job.brand_style.ilike(search_value),
            )
        )
    if start_date:
        try:
            query = query.filter(Job.created_at >= datetime.fromisoformat(start_date))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date format")
    if end_date:
        try:
            query = query.filter(Job.created_at <= datetime.fromisoformat(end_date))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date format")

    jobs = query.order_by(Job.created_at.desc()).limit(200).all()
    return {"jobs": [job_to_dict(job) for job in jobs]}


@app.get("/jobs/{job_id}")
@app.get("/api/jobs/{job_id}")
def get_job_details(
    job_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    job = db.query(Job).filter(Job.job_id == job_id, Job.business_id == business_id).first()
    if not job:
        fallback_job = redis_store.get_job(job_id)
        if fallback_job and fallback_job.job_id.startswith(f"job_{business_id}_"):
            return fallback_job.dict()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    assets = [asset for asset in job.assets if not asset.is_deleted]
    return job_to_dict(job, assets)


@app.get("/assets")
@app.get("/api/assets")
def list_assets(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    asset_type: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Asset).join(Job).filter(Job.business_id == business_id, Asset.is_deleted == False)

    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    if preset_id:
        query = query.filter(Job.preset_id == preset_id)
    if output_format:
        query = query.filter(Job.output_format == output_format)
    if search:
        query = query.filter(Asset.label.ilike(f"%{search}%"))
    if start_date:
        try:
            query = query.filter(Asset.created_at >= datetime.fromisoformat(start_date))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid start_date format")
    if end_date:
        try:
            query = query.filter(Asset.created_at <= datetime.fromisoformat(end_date))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid end_date format")

    assets = query.order_by(Asset.created_at.desc()).limit(200).all()
    return {"assets": [asset_to_dict(asset) for asset in assets]}


@app.get("/gallery")
@app.get("/api/gallery")
def get_gallery(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Asset).join(Job).filter(Job.business_id == business_id, Asset.is_deleted == False)
    assets = query.order_by(Asset.created_at.desc()).limit(200).all()
    return {"assets": [asset_to_dict(asset) for asset in assets]}


@app.delete("/assets/{asset_id}")
@app.delete("/api/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    asset = db.query(Asset).join(Job).filter(Asset.id == asset_id, Job.business_id == business_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    asset.is_deleted = True
    asset.deleted_at = datetime.utcnow()
    asset.updated_at = datetime.utcnow()
    db.commit()
    return {"detail": "deleted"}

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        extra={"postgres_host": settings.postgres_host, "postgres_db": settings.postgres_db}
    )

# Middleware to generate and propagate correlation IDs
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Generate correlation ID and propagate through request headers."""
    correlation_id = request.headers.get("X-Correlation-ID") or generate_correlation_id()
    
    # Set correlation ID in environment for this request
    set_correlation_id(correlation_id)
    
    # Add to request state
    request.state.correlation_id = correlation_id
    
    # Log request with correlation ID
    log_event(
        logger,
        event_type="request",
        job_id=None,
        status="started",
        message=f"{request.method} {request.url.path}",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method
    )
    
    response = await call_next(request)
    
    # Log response
    log_event(
        logger,
        event_type="response",
        job_id=None,
        status="completed",
        message=f"{request.method} {request.url.path} - {response.status_code}",
        correlation_id=correlation_id,
        status_code=response.status_code
    )
    
    return response

# Initialize services
redis_store = RedisJobStore()
storage = R2Storage()
api_auth = APIKeyAuth()
usage_tracker = UsageTracker()

# Redis connection for rate limiting
rate_limit_redis = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    password=os.getenv('REDIS_PASSWORD', ''),
    decode_responses=True
)

# Celery configuration
celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

celery.conf.task_queues = (
    Queue("download"),
    Queue("preprocess"),
    Queue("generate"),
    Queue("upload"),
    Queue("status"),
)

celery.conf.task_routes = {
    "worker.process_job": {"queue": "generate"},
    "tasks.download_input_image": {"queue": "download"},
    "tasks.preprocess_image": {"queue": "preprocess"},
    "tasks.generate_images": {"queue": "generate"},
    "tasks.upload_results": {"queue": "upload"},
    "tasks.update_job_status": {"queue": "status"},
}
celery.conf.task_default_queue = "generate"

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/rate_limit/{business_id}")
def get_rate_limit_status(business_id: str):
    """Get current rate limit status for a business"""
    key = f"rate_limit:{business_id}"
    current = rate_limit_redis.get(key)
    return {
        "business_id": business_id,
        "current_requests": int(current) if current else 0,
        "limit": 10,
        "reset_time": "1 minute"
    }

async def check_rate_limit(business_id: str):
    """Check and update rate limit for business"""
    key = f"rate_limit:{business_id}"
    
    # Increment request count and set expiration atomically
    current = rate_limit_redis.incr(key)
    if current == 1:
        rate_limit_redis.expire(key, 60)
    
    if current > 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 10 requests per minute."
        )

@app.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_image(
    request: GenerateRequest,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Generate images from input image and prompt"""
    try:
        await check_rate_limit(business_id)

        job_id = f"job_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"
        redis_store.create_job(job_id, business_id, request)
        try:
            create_job_record(db, job_id, business_id, request)
        except Exception:
            logger.warning("Could not persist job record to database", exc_info=True)

        log_event(
            logger,
            event_type="queued",
            job_id=job_id,
            status="pending",
            message="Job queued for processing",
            business_id=business_id,
            image_url=request.image_url,
            prompt=request.prompt,
            preset_id=request.preset_id,
            use_case=request.use_case.value,
            product_category=request.product_category.value,
            brand_style=request.brand_style,
            output_format=request.output_format.value,
            mode=request.mode.value,
            num_outputs=request.num_outputs,
        )

        celery.send_task(
            "worker.process_job",
            args=[job_id, request.image_url, request.prompt, business_id, request.num_outputs],
            kwargs={
                "preset_id": request.preset_id,
                "use_case": request.use_case.value,
                "product_category": request.product_category.value,
                "brand_style": request.brand_style,
                "output_format": request.output_format.value,
                "mode": request.mode.value,
                "callback_url": request.callback_url,
                "metadata": request.metadata or {},
                "correlation_id": getattr(http_request.state, "correlation_id", None),
            },
            queue="generate",
        )

        created_job = redis_store.get_job(job_id)
        if created_job is None:
            raise HTTPException(status_code=500, detail="Failed to create job record")
        return created_job
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logger,
            event_type="failed",
            job_id=None,
            status="error",
            message=f"Job submission failed: {str(e)}",
            error=str(e)
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/batch/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_batch(
    request: BatchGenerateRequest,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    """Create a batch of generation jobs using shared settings."""
    try:
        await check_rate_limit(business_id)

        batch_id = f"batch_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"
        batch = create_batch_record(db, batch_id, business_id, request)

        created_items = []
        for index, item in enumerate(request.items):
            job_id = f"job_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"
            child_request = GenerateRequest(
                image_url=item.image_url,
                prompt=request.prompt,
                preset_id=request.preset_id,
                use_case=request.use_case,
                product_category=request.product_category,
                brand_style=request.brand_style,
                output_format=request.output_format,
                mode=request.mode,
                num_outputs=request.num_outputs,
                callback_url=request.callback_url,
                metadata=request.metadata,
            )
            redis_store.create_job(
                job_id,
                business_id,
                child_request,
                batch_id=batch_id,
                item_index=index,
                item_label=item.label,
                input_file_name=item.input_file_name,
                original_image_url=item.image_url,
            )
            try:
                create_job_record(
                    db,
                    job_id,
                    business_id,
                    child_request,
                    batch_id=batch_id,
                    item_index=index,
                    item_label=item.label,
                    input_file_name=item.input_file_name,
                    original_image_url=item.image_url,
                )
            except Exception:
                logger.warning("Could not persist batch job record to database", exc_info=True)

            log_event(
                logger,
                event_type="queued",
                job_id=job_id,
                status="pending",
                message="Batch item queued for processing",
                business_id=business_id,
                image_url=item.image_url,
                prompt=request.prompt,
                preset_id=request.preset_id,
                use_case=request.use_case.value,
                product_category=request.product_category.value,
                brand_style=request.brand_style,
                output_format=request.output_format.value,
                mode=request.mode.value,
                num_outputs=request.num_outputs,
                item_index=index,
            )

            celery.send_task(
                "worker.process_job",
                args=[job_id, item.image_url, request.prompt, business_id, request.num_outputs],
                kwargs={
                    "preset_id": request.preset_id,
                    "use_case": request.use_case.value,
                    "product_category": request.product_category.value,
                    "brand_style": request.brand_style,
                    "output_format": request.output_format.value,
                    "mode": request.mode.value,
                    "callback_url": request.callback_url,
                    "metadata": request.metadata or {},
                    "correlation_id": getattr(http_request.state, "correlation_id", None),
                },
                queue="generate",
            )

            created_items.append({
                "item_index": index,
                "label": item.label,
                "job_id": job_id,
                "status": JobStatus.PENDING.value,
            })

        return {
            "batch_id": batch.batch_id,
            "business_id": batch.business_id,
            "status": batch.status,
            "total_items": batch.total_items,
            "completed_items": 0,
            "failed_items": 0,
            "pending_items": batch.pending_items,
            "progress": 0,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
            "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
            "items": created_items,
        }
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logger,
            event_type="failed",
            job_id=None,
            status="error",
            message=f"Batch submission failed: {str(e)}",
            error=str(e),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.get("/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    batch = db.query(BatchJob).filter(BatchJob.batch_id == batch_id, BatchJob.business_id == business_id).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    jobs = db.query(Job).filter(Job.batch_id == batch_id).all()
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No jobs found for this batch")

    return build_batch_response(batch, jobs)


@app.get("/presets")
def get_presets() -> dict:
    """List available generation presets."""
    return {"presets": list_presets()}


@app.get("/output-formats")
def get_output_formats() -> dict:
    """List output format presets."""
    return {"output_formats": list_output_formats()}


@app.get("/job/{job_id}")
async def get_job_status(
    job_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency)
) -> JobResponse:
    """Get job status and results"""
    job = redis_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    # Verify business ownership
    if not job.job_id.startswith(f"job_{business_id}_"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return job

@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "redis": "connected",
            "r2": "configured"
        }
    }


@app.get("/usage")
async def get_usage(business_id: str, days: int = 7):
    """Get API usage statistics for a business"""
    try:
        stats = usage_tracker.get_usage_stats(business_id, days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    business_id: str = Depends(api_auth.verify_api_key_dependency)
) -> dict:
    """Upload an image to R2 storage"""
    try:
        # Check rate limit
        await check_rate_limit(business_id)
        
        # Read file content
        contents = await file.read()
        
        # Generate unique filename
        timestamp = int(time.time())
        filename = f"{business_id}_{timestamp}_{file.filename}"
        
        # Upload to R2
        url = storage.upload_image(contents, filename)
        
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
