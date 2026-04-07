"""Approval API endpoints for asset review workflows."""
from datetime import datetime
from typing import Optional

from business_presets import GenerationMode, OutputFormat, ProductCategory, UseCase
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.app_state import api_auth
from api.dependencies import get_db
from api.models import GenerateRequest
from api.repositories import get_asset_for_business, get_job_by_id
from api.serializers import asset_to_dict
from api.services.approval import (
    ApprovalError,
    AssetNotFoundError,
    approve_asset,
    get_assets_by_approval_status,
    get_approval_stats,
    reject_asset,
)
from api.services.generation import queue_job

router = APIRouter(prefix="/assets", tags=["approval"])


class RejectionRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/{asset_id}/approve", status_code=status.HTTP_200_OK)
def approve_asset_endpoint(
    asset_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    """Approve an asset owned by the current business."""
    try:
        asset = approve_asset(
            db=db,
            asset_id=asset_id,
            approver_id=business_id,
            business_id=business_id,
        )
        return asset_to_dict(asset)
    except AssetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ApprovalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{asset_id}/reject", status_code=status.HTTP_200_OK)
def reject_asset_endpoint(
    asset_id: int,
    payload: Optional[RejectionRequest] = None,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    """Reject an asset owned by the current business."""
    try:
        asset = reject_asset(
            db=db,
            asset_id=asset_id,
            rejecter_id=business_id,
            business_id=business_id,
            reason=payload.reason if payload else None,
        )
        return asset_to_dict(asset)
    except AssetNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ApprovalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/approval-status", status_code=status.HTTP_200_OK)
def get_assets_by_status(
    status: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    """Get assets by approval status for the current business."""
    assets = get_assets_by_approval_status(
        db=db,
        status=status,
        business_id=business_id,
        limit=limit,
        offset=offset,
    )

    return {
        "assets": [asset_to_dict(asset) for asset in assets],
        "count": len(assets),
    }


@router.get("/approval-stats", status_code=status.HTTP_200_OK)
def get_approval_statistics(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    """Get approval statistics for the current business."""
    stats = get_approval_stats(db=db, business_id=business_id)

    return {
        "stats": stats,
        "total": sum(stats.values()),
    }


@router.post("/{asset_id}/regenerate", status_code=status.HTTP_201_CREATED)
def regenerate_asset(
    asset_id: int,
    http_request: Request,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
) -> dict:
    """Regenerate a variation from an existing asset owned by the current business."""
    asset = get_asset_for_business(db, asset_id, business_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID {asset_id} not found",
        )

    job = get_job_by_id(db, asset.job_id)
    if not job or job.business_id != business_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {asset.job_id} not found",
        )

    metadata = dict(job.job_metadata or {})
    metadata["regenerated_from"] = {
        "source_asset_id": asset.id,
        "source_job_id": job.job_id,
        "source_asset_url": asset.asset_url,
        "requested_at": datetime.utcnow().isoformat(),
    }

    regenerate_request = GenerateRequest(
        image_url=asset.asset_url or job.image_url or job.original_image_url,
        prompt=job.prompt or "",
        preset_id=job.preset_id,
        use_case=UseCase(job.use_case) if job.use_case else UseCase.MAIN_PRODUCT_IMAGE,
        product_category=(
            ProductCategory(job.product_category)
            if job.product_category
            else ProductCategory.GENERAL
        ),
        brand_style=job.brand_style,
        brand_kit_id=job.brand_kit_id,
        brand_kit_snapshot=job.brand_kit_snapshot,
        output_format=(
            OutputFormat(job.output_format)
            if job.output_format
            else OutputFormat.PRODUCT_IMAGE
        ),
        mode=GenerationMode(job.mode) if job.mode else GenerationMode.PRODUCTION,
        num_outputs=job.num_outputs or 1,
        callback_url=job.callback_url,
        metadata=metadata,
    )

    new_job_id = queue_job(
        db,
        regenerate_request,
        business_id,
        http_request,
        batch_id=job.batch_id,
        item_index=job.item_index,
        item_label=job.item_label,
        input_file_name=job.input_file_name,
        original_image_url=asset.asset_url,
    )

    return {
        "message": "Asset regeneration initiated",
        "new_job_id": new_job_id,
        "source_asset_id": asset.id,
        "source_job_id": job.job_id,
    }
