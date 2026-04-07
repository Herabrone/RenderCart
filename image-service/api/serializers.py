from datetime import datetime

from api.app_state import storage
from api.models import JobStatus
from api.models_db import Asset, BatchJob, BrandKit, Job


def asset_to_dict(asset: Asset) -> dict:
    asset_url = asset.asset_url
    if asset.storage_key:
        try:
            asset_url = storage.generate_presigned_url(asset.storage_key)
        except Exception:
            asset_url = asset.asset_url

    return {
        "id": asset.id,
        "job_id": asset.job.job_id if asset.job else None,
        "asset_type": asset.asset_type,
        "label": asset.label,
        "asset_url": asset_url,
        "storage_key": asset.storage_key,
        "output_index": asset.output_index,
        "width": asset.width,
        "height": asset.height,
        "file_format": asset.file_format,
        "is_deleted": asset.is_deleted,
        "asset_metadata": asset.asset_metadata,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        "approval_status": asset.approval_status,
        "rejection_reason": asset.rejection_reason,
        "approved_by": asset.approved_by,
        "approved_at": asset.approved_at.isoformat() if asset.approved_at else None,
        "rejected_by": asset.rejected_by,
        "rejected_at": asset.rejected_at.isoformat() if asset.rejected_at else None,
        "shopify_product_id": asset.shopify_product_id,
        "shopify_media_id": asset.shopify_media_id,
        "shopify_publish_status": asset.shopify_publish_status,
        "shopify_error_message": asset.shopify_error_message,
        "shopify_published_at": asset.shopify_published_at.isoformat() if asset.shopify_published_at else None,
    }


def brand_kit_to_dict(brand_kit: BrandKit) -> dict:
    return {
        "id": brand_kit.id,
        "business_id": brand_kit.business_id,
        "name": brand_kit.name,
        "background": brand_kit.background,
        "lighting": brand_kit.lighting,
        "tone": brand_kit.tone,
        "framing": brand_kit.framing,
        "created_at": brand_kit.created_at.isoformat() if brand_kit.created_at else None,
        "updated_at": brand_kit.updated_at.isoformat() if brand_kit.updated_at else None,
    }


def shopify_store_to_dict(store) -> dict:
    return {
        "id": store.id,
        "business_id": store.business_id,
        "shop_domain": store.shop_domain,
        "scopes": store.scopes,
        "status": store.status,
        "created_at": store.created_at.isoformat() if store.created_at else None,
        "updated_at": store.updated_at.isoformat() if store.updated_at else None,
    }


def job_to_dict(job: Job, include_assets: bool = False) -> dict:
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
        "brand_kit_id": job.brand_kit_id,
        "brand_kit_snapshot": job.brand_kit_snapshot,
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
    if include_assets:
        result["assets"] = [asset_to_dict(asset) for asset in job.assets if not asset.is_deleted]
    return result


def compute_batch_status(jobs: list[Job]) -> str:
    statuses = {job.status for job in jobs}
    if jobs and statuses == {JobStatus.COMPLETED.value}:
        return JobStatus.COMPLETED.value
    if any(status in {JobStatus.PENDING.value, JobStatus.PROCESSING.value} for status in statuses):
        return JobStatus.PROCESSING.value
    if any(status == JobStatus.FAILED.value for status in statuses):
        return JobStatus.FAILED.value
    return JobStatus.PENDING.value


def build_batch_response(batch: BatchJob) -> dict:
    jobs = list(batch.jobs)
    completed_items = sum(1 for job in jobs if job.status == JobStatus.COMPLETED.value)
    failed_items = sum(1 for job in jobs if job.status == JobStatus.FAILED.value)
    pending_items = sum(1 for job in jobs if job.status == JobStatus.PENDING.value)
    total_items = len(jobs)
    progress = round(sum(job.progress or 0 for job in jobs) / total_items) if total_items else 0

    items = []
    ordered_jobs = sorted(
        jobs,
        key=lambda job: (
            job.item_index if job.item_index is not None else 0,
            job.created_at or datetime.min,
        ),
    )
    for job in ordered_jobs:
        items.append(
            {
                "item_index": job.item_index,
                "label": job.item_label,
                "job_id": job.job_id,
                "status": job.status,
                "progress": job.progress or 0,
                "error": job.error,
                "output_urls": [
                    asset_to_dict(asset)["asset_url"]
                    for asset in job.assets
                    if not asset.is_deleted
                ],
                "batch_id": batch.batch_id,
            }
        )

    return {
        "batch_id": batch.batch_id,
        "business_id": batch.business_id,
        "status": compute_batch_status(jobs),
        "total_items": total_items,
        "completed_items": completed_items,
        "failed_items": failed_items,
        "pending_items": pending_items,
        "progress": progress,
        "prompt": batch.prompt,
        "preset_id": batch.preset_id,
        "use_case": batch.use_case,
        "product_category": batch.product_category,
        "brand_style": batch.brand_style,
        "brand_kit_id": batch.brand_kit_id,
        "brand_kit_snapshot": batch.brand_kit_snapshot,
        "output_format": batch.output_format,
        "mode": batch.mode,
        "metadata": batch.batch_metadata,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "items": items,
    }
