"""
Approval API endpoints for asset approval workflow.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models import JobStatus
from api.models_db import Asset, Job
from api.repositories import (
    create_job,
    get_asset_by_id,
    get_job_by_id,
    get_job_by_job_id,
)
from api.serializers import asset_to_dict
from api.services.approval import (
    ApprovalError,
    approve_asset,
    get_assets_by_approval_status,
    get_approval_stats,
    reject_asset,
)

router = APIRouter(prefix="/assets", tags=["approval"])


@router.post("/{asset_id}/approve", status_code=status.HTTP_200_OK)
def approve_asset_endpoint(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Approve an asset.
    
    Args:
        asset_id: ID of the asset to approve
        current_user: Current authenticated user
        
    Returns:
        Approved asset details
        
    Raises:
        HTTPException: If asset not found or already approved/rejected
    """
    try:
        asset = approve_asset(
            db=db,
            asset_id=asset_id,
            approver_id=current_user["sub"],
        )
        return asset_to_dict(asset)
    except ApprovalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{asset_id}/reject", status_code=status.HTTP_200_OK)
def reject_asset_endpoint(
    asset_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Reject an asset.
    
    Args:
        asset_id: ID of the asset to reject
        reason: Optional reason for rejection
        current_user: Current authenticated user
        
    Returns:
        Rejected asset details
        
    Raises:
        HTTPException: If asset not found or already approved/rejected
    """
    try:
        asset = reject_asset(
            db=db,
            asset_id=asset_id,
            rejecter_id=current_user["sub"],
            reason=reason,
        )
        return asset_to_dict(asset)
    except ApprovalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/approval-status", status_code=status.HTTP_200_OK)
def get_assets_by_status(
    status: str,
    business_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Get assets by approval status.
    
    Args:
        status: Approval status to filter by (pending, approved, rejected)
        business_id: Optional business ID to filter by
        limit: Maximum number of assets to return
        offset: Offset for pagination
        current_user: Current authenticated user
        
    Returns:
        List of assets matching the criteria
    """
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
    business_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Get approval statistics.
    
    Args:
        business_id: Optional business ID to filter by
        current_user: Current authenticated user
        
    Returns:
        Approval statistics
    """
    stats = get_approval_stats(db=db, business_id=business_id)
    
    return {
        "stats": stats,
        "total": sum(stats.values()),
    }


@router.post("/{asset_id}/regenerate", status_code=status.HTTP_201_CREATED)
def regenerate_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Regenerate an asset (create a new job based on the original job).
    
    Args:
        asset_id: ID of the asset to regenerate
        current_user: Current authenticated user
        
    Returns:
        New job details
        
    Raises:
        HTTPException: If asset not found or job not found
    """
    # Get the asset
    asset = get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID {asset_id} not found",
        )
    
    # Get the original job
    job = get_job_by_id(db, asset.job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID {asset.job_id} not found",
        )
    
    # Create a new job based on the original job
    new_job = create_job(
        db=db,
        job_id=None,  # Let the system generate a new job ID
        status=JobStatus.PENDING.value,
        batch_id=job.batch_id,
        item_index=job.item_index,
        item_label=job.item_label,
        input_file_name=job.input_file_name,
        original_image_url=job.original_image_url,
        image_url=None,
        prompt=job.prompt,
        preset_id=job.preset_id,
        use_case=job.use_case,
        product_category=job.product_category,
        brand_style=job.brand_style,
        brand_kit_id=job.brand_kit_id,
        brand_kit_snapshot=job.brand_kit_snapshot,
        output_format=job.output_format,
        mode=job.mode,
        num_outputs=job.num_outputs,
        callback_url=job.callback_url,
        job_metadata=job.job_metadata,
        actual_model=job.actual_model,
        inference_config_used=job.inference_config_used,
        progress=0,
        step=None,
        error=None,
        business_id=job.business_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    db.commit()
    db.refresh(new_job)
    
    return {
        "message": "Asset regeneration initiated",
        "new_job_id": new_job.job_id,
    }
