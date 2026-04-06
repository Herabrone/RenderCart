import uuid
from os import path

from config import settings
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from api.app_state import api_auth, storage, usage_tracker
from api.rate_limit import check_rate_limit, get_rate_limit_status

router = APIRouter(tags=["operations"])


@router.get("/")
def root():
    return {"status": "running"}


@router.get("/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "services": {
            "redis": "configured",
            "r2": "configured" if storage.configured else "not_configured",
        },
    }


@router.get("/usage")
async def get_usage(
    days: int = Query(default=7, ge=1, le=30),
    business_id: str = Depends(api_auth.verify_api_key_dependency),
):
    try:
        return usage_tracker.get_usage_stats(business_id, days)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/rate_limit/{requested_business_id}")
def rate_limit_status(
    requested_business_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
):
    if requested_business_id != business_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return get_rate_limit_status(business_id)


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    business_id: str = Depends(api_auth.verify_api_key_dependency),
) -> dict:
    await check_rate_limit(business_id)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image uploads are supported",
        )

    try:
        contents = await file.read()
        if len(contents) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "File size exceeds the "
                    f"{settings.max_upload_bytes // (1024 * 1024)}MB limit"
                ),
            )

        safe_name = path.basename(file.filename or "upload.png")
        filename = f"{business_id}/uploads/{uuid.uuid4().hex}_{safe_name}"
        url = storage.upload_image(contents, filename, content_type=file.content_type)
        return {"url": url}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
