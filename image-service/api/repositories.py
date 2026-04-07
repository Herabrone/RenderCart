from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from api.models import JobStatus
from api.models_db import Asset, BatchJob, BrandKit, Job


def list_batches(
    db: Session,
    business_id: str,
    *,
    search: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int,
    offset: int,
) -> list[BatchJob]:
    query = (
        db.query(BatchJob)
        .options(selectinload(BatchJob.jobs).selectinload(Job.assets))
        .filter(BatchJob.business_id == business_id)
    )
    if preset_id:
        query = query.filter(BatchJob.preset_id == preset_id)
    if output_format:
        query = query.filter(BatchJob.output_format == output_format)
    if search:
        search_value = f"%{search}%"
        query = query.filter(
            or_(
                BatchJob.prompt.ilike(search_value),
                BatchJob.brand_style.ilike(search_value),
                BatchJob.product_category.ilike(search_value),
            )
        )
    if start_date:
        query = query.filter(BatchJob.created_at >= start_date)
    if end_date:
        query = query.filter(BatchJob.created_at <= end_date)
    return query.order_by(BatchJob.created_at.desc()).offset(offset).limit(limit).all()


def get_batch(db: Session, batch_id: str, business_id: str) -> Optional[BatchJob]:
    return (
        db.query(BatchJob)
        .options(selectinload(BatchJob.jobs).selectinload(Job.assets))
        .filter(BatchJob.batch_id == batch_id, BatchJob.business_id == business_id)
        .first()
    )


def list_brand_kits(db: Session, business_id: str) -> list[BrandKit]:
    return (
        db.query(BrandKit)
        .filter(BrandKit.business_id == business_id)
        .order_by(BrandKit.updated_at.desc(), BrandKit.id.desc())
        .all()
    )


def get_brand_kit(db: Session, brand_kit_id: int, business_id: str) -> Optional[BrandKit]:
    return (
        db.query(BrandKit)
        .filter(BrandKit.id == brand_kit_id, BrandKit.business_id == business_id)
        .first()
    )


def list_jobs(
    db: Session,
    business_id: str,
    *,
    search: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    status_value: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int,
    offset: int,
) -> list[Job]:
    query = db.query(Job).filter(Job.business_id == business_id)
    if preset_id:
        query = query.filter(Job.preset_id == preset_id)
    if output_format:
        query = query.filter(Job.output_format == output_format)
    if status_value:
        query = query.filter(Job.status == status_value)
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
        query = query.filter(Job.created_at >= start_date)
    if end_date:
        query = query.filter(Job.created_at <= end_date)
    return query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()


def get_job(db: Session, job_id: str, business_id: str) -> Optional[Job]:
    return (
        db.query(Job)
        .options(selectinload(Job.assets))
        .filter(Job.job_id == job_id, Job.business_id == business_id)
        .first()
    )


def get_job_by_id(db: Session, job_pk: int) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_pk).first()


def list_assets(
    db: Session,
    business_id: str,
    *,
    asset_type: Optional[str] = None,
    preset_id: Optional[str] = None,
    output_format: Optional[str] = None,
    approval_status: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int,
    offset: int,
) -> list[Asset]:
    query = (
        db.query(Asset)
        .join(Job)
        .options(selectinload(Asset.job))
        .filter(Job.business_id == business_id, Asset.is_deleted.is_(False))
    )
    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    if preset_id:
        query = query.filter(Job.preset_id == preset_id)
    if output_format:
        query = query.filter(Job.output_format == output_format)
    if approval_status:
        query = query.filter(Asset.approval_status == approval_status)
    if search:
        query = query.filter(Asset.label.ilike(f"%{search}%"))
    if start_date:
        query = query.filter(Asset.created_at >= start_date)
    if end_date:
        query = query.filter(Asset.created_at <= end_date)
    return query.order_by(Asset.created_at.desc()).offset(offset).limit(limit).all()


def get_gallery_assets(db: Session, business_id: str, *, limit: int, offset: int) -> list[Asset]:
    return (
        db.query(Asset)
        .join(Job)
        .options(selectinload(Asset.job))
        .filter(Job.business_id == business_id, Asset.is_deleted.is_(False))
        .order_by(Asset.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_asset_for_business(db: Session, asset_id: int, business_id: str) -> Optional[Asset]:
    return (
        db.query(Asset)
        .join(Job)
        .filter(Asset.id == asset_id, Job.business_id == business_id)
        .first()
    )


def get_failed_batch_jobs(db: Session, batch_id: str) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.batch_id == batch_id, Job.status == JobStatus.FAILED.value)
        .all()
    )


# ---------------------------------------------------------------------------
# Shopify store repository
# ---------------------------------------------------------------------------

from api.models_db import ShopifyStore  # noqa: E402 (placed here to avoid circular imports)


def list_shopify_stores(db: Session, business_id: str) -> list[ShopifyStore]:
    return (
        db.query(ShopifyStore)
        .filter(ShopifyStore.business_id == business_id)
        .order_by(ShopifyStore.created_at.desc())
        .all()
    )


def get_shopify_store(db: Session, store_id: int, business_id: str) -> Optional[ShopifyStore]:
    return (
        db.query(ShopifyStore)
        .filter(ShopifyStore.id == store_id, ShopifyStore.business_id == business_id)
        .first()
    )


def get_shopify_store_by_domain(
    db: Session, shop_domain: str, business_id: str
) -> Optional[ShopifyStore]:
    return (
        db.query(ShopifyStore)
        .filter(
            ShopifyStore.shop_domain == shop_domain,
            ShopifyStore.business_id == business_id,
        )
        .first()
    )


def mark_store_disconnected(
    db: Session,
    store_id: int,
    reason: str = "unknown",
) -> None:
    """Sets a store's status to 'disconnected' without deleting the record.

    Called automatically when Shopify returns 401, indicating the token has
    been revoked or has expired. The record is retained so the merchant can
    see which store needs reconnection.
    """
    store = db.query(ShopifyStore).filter(ShopifyStore.id == store_id).first()
    if store and store.status == "active":
        store.status = "disconnected"
        store.updated_at = datetime.utcnow()
        db.commit()

