import os
import re
import tempfile
import zipfile
from datetime import datetime
from typing import Optional

import requests
from business_presets import GenerationMode, OutputFormat, ProductCategory, UseCase
from config import settings
from fastapi import HTTPException, Request, status
from logging_config import log_event
from sqlalchemy.orm import Session
from url_safety import validate_public_http_url

from api.app_state import celery, logger, redis_store, storage
from api.ids import generate_batch_id, generate_job_id
from api.models import BatchGenerateRequest, GenerateRequest, JobStatus
from api.models_db import Asset, BatchJob, Job


def validate_generate_request(request: GenerateRequest) -> None:
    try:
        validate_public_http_url(request.image_url, "image_url")
        if request.callback_url:
            validate_public_http_url(request.callback_url, "callback_url")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def validate_batch_request(request: BatchGenerateRequest) -> None:
    try:
        if request.callback_url:
            validate_public_http_url(request.callback_url, "callback_url")
        for index, item in enumerate(request.items):
            validate_public_http_url(item.image_url, f"items[{index}].image_url")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


def create_job_record(
    db: Session,
    job_id: str,
    business_id: str,
    request: GenerateRequest,
    *,
    batch_id: Optional[str] = None,
    item_index: Optional[int] = None,
    item_label: Optional[str] = None,
    input_file_name: Optional[str] = None,
    original_image_url: Optional[str] = None,
) -> Job:
    job = Job(
        job_id=job_id,
        business_id=business_id,
        batch_id=batch_id,
        item_index=item_index,
        item_label=item_label,
        input_file_name=input_file_name,
        original_image_url=original_image_url,
        status=JobStatus.PENDING.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        image_url=request.image_url,
        prompt=request.prompt,
        preset_id=request.preset_id,
        use_case=request.use_case.value,
        product_category=request.product_category.value,
        brand_style=request.brand_style,
        output_format=request.output_format.value,
        mode=request.mode.value,
        num_outputs=request.num_outputs,
        callback_url=request.callback_url,
        job_metadata=request.metadata or {},
        progress=0,
        step="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def create_batch_record(
    db: Session,
    batch_id: str,
    business_id: str,
    request: BatchGenerateRequest,
) -> BatchJob:
    batch = BatchJob(
        batch_id=batch_id,
        business_id=business_id,
        status=JobStatus.PENDING.value,
        total_items=len(request.items),
        completed_items=0,
        failed_items=0,
        pending_items=len(request.items),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        batch_metadata=request.metadata or {},
        prompt=request.prompt,
        preset_id=request.preset_id,
        use_case=request.use_case.value,
        product_category=request.product_category.value,
        brand_style=request.brand_style,
        output_format=request.output_format.value,
        mode=request.mode.value,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def _send_generation_task(
    job_id: str,
    request: GenerateRequest,
    business_id: str,
    correlation_id: Optional[str],
) -> None:
    celery.send_task(
        "worker.process_job",
        args=[job_id, request.image_url, request.prompt, business_id, request.num_outputs],
        kwargs={
            "preset_id": request.preset_id,
            "use_case": request.use_case.value,
            "product_category": request.product_category.value,
            "brand_style": request.brand_style,
            "output_format": request.output_format.value,
            "mode": request.mode.value,
            "callback_url": request.callback_url,
            "metadata": request.metadata or {},
            "correlation_id": correlation_id,
        },
        queue="generate",
    )


def queue_job(
    db: Session,
    request: GenerateRequest,
    business_id: str,
    http_request: Request,
    *,
    batch_id: Optional[str] = None,
    item_index: Optional[int] = None,
    item_label: Optional[str] = None,
    input_file_name: Optional[str] = None,
    original_image_url: Optional[str] = None,
) -> str:
    validate_generate_request(request)

    job_id = generate_job_id(business_id)
    redis_store.create_job(
        job_id,
        business_id,
        request,
        batch_id=batch_id,
        item_index=item_index,
        item_label=item_label,
        input_file_name=input_file_name,
        original_image_url=original_image_url,
    )
    try:
        create_job_record(
            db,
            job_id,
            business_id,
            request,
            batch_id=batch_id,
            item_index=item_index,
            item_label=item_label,
            input_file_name=input_file_name,
            original_image_url=original_image_url,
        )
    except Exception:
        logger.warning("Could not persist job record to database", exc_info=True)

    log_event(
        logger,
        event_type="queued",
        job_id=job_id,
        status="pending",
        message="Job queued for processing",
        business_id=business_id,
        image_url=request.image_url,
        prompt=request.prompt,
        preset_id=request.preset_id,
        use_case=request.use_case.value,
        product_category=request.product_category.value,
        brand_style=request.brand_style,
        output_format=request.output_format.value,
        mode=request.mode.value,
        num_outputs=request.num_outputs,
        item_index=item_index,
    )

    _send_generation_task(
        job_id,
        request,
        business_id,
        getattr(http_request.state, "correlation_id", None),
    )
    return job_id


def queue_single_job(
    db: Session,
    request: GenerateRequest,
    business_id: str,
    http_request: Request,
):
    job_id = queue_job(db, request, business_id, http_request)
    created_job = redis_store.get_job(job_id)
    if created_job is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job record",
        )
    return created_job


def queue_batch(
    db: Session,
    request: BatchGenerateRequest,
    business_id: str,
    http_request: Request,
) -> dict:
    validate_batch_request(request)

    batch_id = generate_batch_id(business_id)
    batch = create_batch_record(db, batch_id, business_id, request)

    created_items = []
    for index, item in enumerate(request.items):
        child_request = GenerateRequest(
            image_url=item.image_url,
            prompt=request.prompt,
            preset_id=request.preset_id,
            use_case=request.use_case,
            product_category=request.product_category,
            brand_style=request.brand_style,
            output_format=request.output_format,
            mode=request.mode,
            num_outputs=request.num_outputs,
            callback_url=request.callback_url,
            metadata=request.metadata,
        )
        job_id = queue_job(
            db,
            child_request,
            business_id,
            http_request,
            batch_id=batch_id,
            item_index=index,
            item_label=item.label,
            input_file_name=item.input_file_name,
            original_image_url=item.image_url,
        )
        created_items.append(
            {
                "item_index": index,
                "label": item.label,
                "job_id": job_id,
                "status": JobStatus.PENDING.value,
            }
        )

    return {
        "batch_id": batch.batch_id,
        "business_id": batch.business_id,
        "status": batch.status,
        "total_items": batch.total_items,
        "completed_items": 0,
        "failed_items": 0,
        "pending_items": batch.pending_items,
        "progress": 0,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "items": created_items,
    }


def retry_failed_batch_jobs(
    db: Session,
    batch: BatchJob,
    failed_jobs: list[Job],
    http_request: Request,
    keep_item_labels: bool,
) -> list[dict]:
    requeued_items = []
    for job in failed_jobs:
        child_request = GenerateRequest(
            image_url=job.image_url,
            prompt=job.prompt or batch.prompt or "",
            preset_id=job.preset_id or batch.preset_id or settings.default_preset_id,
            use_case=UseCase(job.use_case) if job.use_case else UseCase(batch.use_case),
            product_category=ProductCategory(job.product_category)
            if job.product_category
            else ProductCategory(batch.product_category),
            brand_style=job.brand_style or batch.brand_style,
            output_format=(
                OutputFormat(job.output_format)
                if job.output_format
                else OutputFormat(batch.output_format)
            ),
            mode=GenerationMode(job.mode) if job.mode else GenerationMode(batch.mode),
            num_outputs=job.num_outputs or 1,
            callback_url=job.callback_url,
            metadata=job.job_metadata,
        )
        new_job_id = queue_job(
            db,
            child_request,
            batch.business_id,
            http_request,
            batch_id=batch.batch_id,
            item_index=job.item_index,
            item_label=job.item_label if keep_item_labels else None,
            input_file_name=job.input_file_name,
            original_image_url=job.original_image_url,
        )
        requeued_items.append(
            {
                "item_index": job.item_index,
                "old_job_id": job.job_id,
                "new_job_id": new_job_id,
                "label": job.item_label,
            }
        )

    batch.updated_at = datetime.utcnow()
    db.commit()
    return requeued_items


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_\- ]+", "_", value or "item")
    return cleaned.strip()[:128] or "item"


def get_asset_filename(job: Job, asset: Asset) -> str:
    label_suffix = job.item_index if job.item_index is not None else job.id
    label = sanitize_name(job.item_label or f"item_{label_suffix}")
    file_name = sanitize_name(asset.label or f"output_{asset.output_index or asset.id}")
    if asset.storage_key:
        extension = os.path.splitext(asset.storage_key)[1]
    else:
        extension = os.path.splitext(asset.asset_url.split("?", 1)[0])[1]
    extension = extension or f".{(asset.file_format or 'png').lower()}"
    return f"{label}/{file_name}{extension}"


def generate_batch_zip(jobs: list[Job]):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_file.close()

    try:
        with zipfile.ZipFile(
            temp_file.name,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as zip_file:
            for job in jobs:
                if job.status != JobStatus.COMPLETED.value:
                    continue
                for asset in [item for item in job.assets if not item.is_deleted]:
                    try:
                        if asset.storage_key:
                            payload = storage.download_bytes(asset.storage_key)
                        else:
                            response = requests.get(
                                asset.asset_url,
                                timeout=settings.request_timeout_seconds,
                            )
                            response.raise_for_status()
                            payload = response.content
                        zip_file.writestr(get_asset_filename(job, asset), payload)
                    except Exception:
                        logger.warning(
                            "Failed to include asset in batch ZIP",
                            extra={
                                "job_id": job.job_id,
                                "asset_url": asset.asset_url,
                                "storage_key": asset.storage_key,
                            },
                            exc_info=True,
                        )

        def file_iterator():
            with open(temp_file.name, "rb") as file_handle:
                while True:
                    chunk = file_handle.read(8192)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.unlink(temp_file.name)
            except OSError:
                pass

        return file_iterator()
    except Exception:
        try:
            os.unlink(temp_file.name)
        except OSError:
            pass
        raise
