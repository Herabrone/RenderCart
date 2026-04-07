"""
Approval service for handling asset approval workflow.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.models_db import Asset, Job
from api.repositories import get_asset_by_id


class ApprovalError(Exception):
    """Base exception for approval-related errors."""
    pass


class AssetNotFoundError(ApprovalError):
    """Raised when an asset is not found."""
    pass


class NotAuthorizedError(ApprovalError):
    """Raised when the user is not authorized to perform the action."""
    pass


class InvalidApprovalStatusError(ApprovalError):
    """Raised when an invalid approval status is provided."""
    pass


def approve_asset(
    db: Session,
    asset_id: int,
    approver_id: str,
) -> Asset:
    """
    Approve an asset.
    
    Args:
        db: Database session
        asset_id: ID of the asset to approve
        approver_id: ID of the user approving the asset
        
    Returns:
        The approved asset
        
    Raises:
        AssetNotFoundError: If the asset does not exist
        InvalidApprovalStatusError: If the asset is already approved or rejected
    """
    asset = get_asset_by_id(db, asset_id)
    if not asset:
        raise AssetNotFoundError(f"Asset with ID {asset_id} not found")
    
    # Check if asset is already approved or rejected
    if asset.approval_status in ["approved", "rejected"]:
        raise InvalidApprovalStatusError(
            f"Cannot approve asset with status {asset.approval_status}"
        )
    
    # Update approval status
    asset.approval_status = "approved"
    asset.approved_by = approver_id
    asset.approved_at = datetime.utcnow()
    
    db.commit()
    db.refresh(asset)
    
    return asset


def reject_asset(
    db: Session,
    asset_id: int,
    rejecter_id: str,
    reason: Optional[str] = None,
) -> Asset:
    """
    Reject an asset.
    
    Args:
        db: Database session
        asset_id: ID of the asset to reject
        rejecter_id: ID of the user rejecting the asset
        reason: Optional reason for rejection
        
    Returns:
        The rejected asset
        
    Raises:
        AssetNotFoundError: If the asset does not exist
        InvalidApprovalStatusError: If the asset is already approved or rejected
    """
    asset = get_asset_by_id(db, asset_id)
    if not asset:
        raise AssetNotFoundError(f"Asset with ID {asset_id} not found")
    
    # Check if asset is already approved or rejected
    if asset.approval_status in ["approved", "rejected"]:
        raise InvalidApprovalStatusError(
            f"Cannot reject asset with status {asset.approval_status}"
        )
    
    # Update rejection status
    asset.approval_status = "rejected"
    asset.rejection_reason = reason
    asset.rejected_by = rejecter_id
    asset.rejected_at = datetime.utcnow()
    
    db.commit()
    db.refresh(asset)
    
    return asset


def get_assets_by_approval_status(
    db: Session,
    status: str,
    business_id: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> list[Asset]:
    """
    Get assets by approval status.
    
    Args:
        db: Database session
        status: Approval status to filter by (pending, approved, rejected)
        business_id: Optional business ID to filter by
        limit: Maximum number of assets to return
        offset: Offset for pagination
        
    Returns:
        List of assets matching the criteria
    """
    query = db.query(Asset).filter(Asset.approval_status == status)
    
    if business_id:
        query = query.join(Asset.job).filter(Job.business_id == business_id)
    
    if limit is not None:
        query = query.limit(limit)
    
    if offset is not None:
        query = query.offset(offset)
    
    return query.all()


def get_approval_stats(
    db: Session,
    business_id: Optional[str] = None,
) -> dict:
    """
    Get approval statistics.
    
    Args:
        db: Database session
        business_id: Optional business ID to filter by
        
    Returns:
        Dictionary with approval statistics
    """
    query = db.query(Asset.approval_status, func.count(Asset.id))
