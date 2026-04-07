from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.app_state import api_auth
from api.dependencies import get_db
from api.models import BrandKitCreateRequest, BrandKitUpdateRequest
from api.models_db import BrandKit
from api.repositories import get_brand_kit, list_brand_kits
from api.serializers import brand_kit_to_dict

router = APIRouter(tags=["brand-kits"])


@router.get("/brand-kits")
def get_brand_kits(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    return {"brand_kits": [brand_kit_to_dict(item) for item in list_brand_kits(db, business_id)]}


@router.post("/brand-kits", status_code=status.HTTP_201_CREATED)
def create_brand_kit(
    request: BrandKitCreateRequest,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    now = datetime.utcnow()
    brand_kit = BrandKit(
        business_id=business_id,
        name=request.name,
        background=request.background,
        lighting=request.lighting,
        tone=request.tone,
        framing=request.framing,
        created_at=now,
        updated_at=now,
    )
    db.add(brand_kit)
    db.commit()
    db.refresh(brand_kit)
    return brand_kit_to_dict(brand_kit)


@router.get("/brand-kits/{brand_kit_id}")
def get_brand_kit_details(
    brand_kit_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    brand_kit = get_brand_kit(db, brand_kit_id, business_id)
    if not brand_kit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    return brand_kit_to_dict(brand_kit)


@router.patch("/brand-kits/{brand_kit_id}")
def update_brand_kit(
    brand_kit_id: int,
    request: BrandKitUpdateRequest,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    brand_kit = get_brand_kit(db, brand_kit_id, business_id)
    if not brand_kit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")

    for field_name in ("name", "background", "lighting", "tone", "framing"):
        value = getattr(request, field_name)
        if value is not None:
            setattr(brand_kit, field_name, value)
    brand_kit.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(brand_kit)
    return brand_kit_to_dict(brand_kit)
