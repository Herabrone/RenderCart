from datetime import datetime
from typing import Optional

from business_presets import list_output_formats, list_presets
from config import settings
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.app_state import api_auth, redis_store
from api.dependencies import get_db
from api.models import BatchGenerateRequest, BatchRetryRequest, GenerateRequest, JobStatus
from api.rate_limit import check_rate_limit
from api.repositories import get_batch, get_failed_batch_jobs, get_job, list_batches, list_jobs
from api.serializers import build_batch_response, job_to_dict
from api.services.generation import (
    generate_batch_zip,
    queue_batch,
    queue_single_job,
    retry_failed_batch_jobs,
)

router = APIRouter(tags=["generation"])


def _parse_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format",
        ) from exc


def _page_limit(limit: int) -> int:
    return max(1, min(limit, settings.max_page_size))


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_image(
    request: GenerateRequest,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    await check_rate_limit(business_id)
    return queue_single_job(db, request, business_id, http_request)


@router.post("/batch/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_batch(
    request: BatchGenerateRequest,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    await check_rate_limit(business_id)
    return queue_batch(db, request, business_id, http_request)


@router.get("/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    batch = get_batch(db, batch_id, business_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return build_batch_response(batch)


@router.get("/batch/{batch_id}/download")
async def download_batch(
    batch_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    batch = get_batch(db, batch_id, business_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    completed_jobs = [job for job in batch.jobs if job.status == JobStatus.COMPLETED.value]
    if not completed_jobs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed items available for download",
        )

    filename = f"rendercart_batch_{batch.batch_id}.zip"
    return StreamingResponse(
        generate_batch_zip(completed_jobs),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/batch/{batch_id}/retry-failed")
async def retry_failed_batch(
    batch_id: str,
    request: BatchRetryRequest,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    batch = get_batch(db, batch_id, business_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    failed_jobs = get_failed_batch_jobs(db, batch_id)
    if not failed_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No failed items found for this batch",
        )

    requeued_items = retry_failed_batch_jobs(
        db,
        batch,
        failed_jobs,
        http_request,
        request.keep_item_labels,
    )
    return {
        "batch_id": batch.batch_id,
        "retry_count": len(requeued_items),
        "requeued_items": requeued_items,
    }


@router.get("/batches")
def get_batches(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    search: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    status_filter: Optional[JobStatus] = Query(default=None, alias="status"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=settings.default_page_size, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    batches = list_batches(
        db,
        business_id,
        search=search,
        preset_id=preset_id,
        output_format=output_format,
        start_date=_parse_datetime(start_date, "start_date"),
        end_date=_parse_datetime(end_date, "end_date"),
        limit=_page_limit(limit),
        offset=offset,
    )
    payload = [build_batch_response(batch) for batch in batches]
    if status_filter:
        payload = [batch for batch in payload if batch["status"] == status_filter.value]
    return {"batches": payload, "limit": _page_limit(limit), "offset": offset}


@router.get("/jobs")
def get_jobs(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    search: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    status_filter: Optional[JobStatus] = Query(default=None, alias="status"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=settings.default_page_size, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    jobs = list_jobs(
        db,
        business_id,
        search=search,
        preset_id=preset_id,
        output_format=output_format,
        status_value=status_filter.value if status_filter else None,
        start_date=_parse_datetime(start_date, "start_date"),
        end_date=_parse_datetime(end_date, "end_date"),
        limit=_page_limit(limit),
        offset=offset,
    )
    return {
        "jobs": [job_to_dict(job) for job in jobs],
        "limit": _page_limit(limit),
        "offset": offset,
    }


@router.get("/jobs/{job_id}")
def get_job_details(
    job_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    job = get_job(db, job_id, business_id)
    if not job:
        fallback_job = redis_store.get_job(job_id)
        if fallback_job and redis_store.get_job_business_id(job_id) == business_id:
            return fallback_job.model_dump()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_dict(job, include_assets=True)


@router.get("/job/{job_id}")
async def get_job_status(
    job_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    redis_job = redis_store.get_job(job_id)
    if redis_job and redis_store.get_job_business_id(job_id) == business_id:
        return redis_job

    job = get_job(db, job_id, business_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job_to_dict(job)


@router.get("/presets")
def get_presets():
    return {"presets": list_presets()}


@router.get("/output-formats")
def get_output_formats():
    return {"output_formats": list_output_formats()}
