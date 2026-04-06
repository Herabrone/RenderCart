from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.app_state import api_auth, redis_store
from api.dependencies import get_db
from api.models import GenerateRequest
from api.repositories import get_job
from api.serializers import asset_to_dict
from api.services.generation import queue_single_job

router = APIRouter(prefix="/v1", tags=["v1"])


@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def v1_generate(
    request: GenerateRequest,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    return queue_single_job(db, request, business_id, http_request)


@router.get("/job/{job_id}")
async def v1_get_job(
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
    asset_urls = [
        asset_to_dict(asset)["asset_url"] for asset in job.assets if not asset.is_deleted
    ]
    return {
        "job_id": job.job_id,
        "status": job.status,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "progress": job.progress,
        "step": job.step,
        "result_urls": asset_urls,
        "output_urls": asset_urls,
        "error": job.error,
    }
