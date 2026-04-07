from datetime import datetime
from typing import Optional

from config import settings
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.app_state import api_auth
from api.dependencies import get_db
from api.repositories import get_asset_for_business, get_gallery_assets, list_assets
from api.serializers import asset_to_dict

router = APIRouter(tags=["assets"])


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


@router.get("/assets")
def get_assets(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    asset_type: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    approval_status: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=settings.default_page_size, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    assets = list_assets(
        db,
        business_id,
        asset_type=asset_type,
        preset_id=preset_id,
        output_format=output_format,
        approval_status=approval_status,
        search=search,
        start_date=_parse_datetime(start_date, "start_date"),
        end_date=_parse_datetime(end_date, "end_date"),
        limit=_page_limit(limit),
        offset=offset,
    )
    return {
        "assets": [asset_to_dict(asset) for asset in assets],
        "limit": _page_limit(limit),
        "offset": offset,
    }


@router.get("/gallery")
def get_gallery(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    limit: int = Query(default=settings.default_page_size, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    assets = get_gallery_assets(db, business_id, limit=_page_limit(limit), offset=offset)
    return {
        "assets": [asset_to_dict(asset) for asset in assets],
        "limit": _page_limit(limit),
        "offset": offset,
    }


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    asset = get_asset_for_business(db, asset_id, business_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    asset.is_deleted = True
    asset.deleted_at = datetime.utcnow()
    asset.updated_at = datetime.utcnow()
    db.commit()
    return {"detail": "deleted"}
