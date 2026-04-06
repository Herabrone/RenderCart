"""Celery worker for the image generation pipeline."""

import logging
import os
import tempfile
import traceback
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional

import requests
from api.db import SessionLocal
from api.models_db import Asset, Job
from business_presets import build_prompt, get_inference_params, get_output_spec
from celery import signature
from celery.exceptions import Ignore
from config import settings
from logging_config import log_event, setup_logging
from model_loader import DEFAULT_MODEL_ID
from task_queue import create_celery_app
from url_safety import validate_public_http_url

from worker.pipeline import generate_images
from worker.status_store import update_job_status
from worker.uploads import upload_results
from worker.webhooks import send_webhook

LOGGER = setup_logging()
logger = logging.getLogger("rendercart.worker")
celery = create_celery_app("rendercart-worker")


def download_input_image(job_id: str, image_url: str) -> str:
    try:
        validate_public_http_url(image_url, "image_url")
        update_job_status(job_id, "processing", progress=10, step="download")

        logger.info("Downloading image", extra={"job_id": job_id, "image_url": image_url})
        response = requests.get(image_url, timeout=settings.request_timeout_seconds)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_file.write(response.content)
            return temp_file.name
    except ValueError as exc:
        error_message = f"Invalid image URL: {exc}"
        update_job_status(job_id, "failed", error=error_message)
        raise Ignore() from exc
    except requests.RequestException as exc:
        error_message = f"Failed to download image: {exc}"
        logger.error("Download failed", extra={"job_id": job_id, "error": error_message})
        update_job_status(job_id, "failed", error=error_message)
        raise


def preprocess_image(job_id: str, image_path: str, output_spec: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from PIL import Image
        from rembg import remove

        update_job_status(job_id, "processing", progress=40, step="preprocess")

        logger.info("Preprocessing image", extra={"job_id": job_id, "image_path": image_path})
        with open(image_path, "rb") as file_handle:
            image_data = file_handle.read()

        image = Image.open(BytesIO(image_data))
        image = remove(image)
        image = image.convert("RGB")
        image = image.resize((output_spec["width"], output_spec["height"]), Image.LANCZOS)

        output_buffer = BytesIO()
        image.save(output_buffer, format="PNG")
        return {"image_bytes": output_buffer.getvalue(), "output_spec": output_spec}
    except Exception as exc:
        error_message = f"Image preprocessing failed: {exc}\n{traceback.format_exc()}"
        logger.error("Preprocessing failed", extra={"job_id": job_id, "error": error_message})
        update_job_status(job_id, "failed", error=error_message)
        raise Ignore() from exc


def finalize_job(
    job_id: str,
    upload_result: Dict[str, Any],
    *,
    output_spec: Optional[Dict[str, Any]] = None,
    actual_model: Optional[str] = None,
    inference_config_used: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    try:
        result = {
            "status": "completed",
            "r2_urls": upload_result.get("r2_urls", []),
            "image_count": upload_result.get("count", 0),
            "completed_at": datetime.utcnow().isoformat(),
        }

        update_job_status(
            job_id,
            "completed",
            progress=100,
            step="completed",
            result_urls=result["r2_urls"],
            actual_model=actual_model,
            inference_config_used=inference_config_used,
        )

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if job:
                for index, item in enumerate(upload_result.get("items", []), start=1):
                    asset = Asset(
                        job_id=job.id,
                        asset_type="generated_output",
                        label=f"Output {index}",
                        asset_url=item["url"],
                        storage_key=item.get("storage_key"),
                        output_index=index,
                        width=output_spec.get("width") if output_spec else None,
                        height=output_spec.get("height") if output_spec else None,
                        file_format=output_spec.get("extension") if output_spec else None,
                        asset_metadata={
                            "preset_id": job.preset_id,
                            "output_format": job.output_format,
                            "use_case": job.use_case,
                            "product_category": job.product_category,
                        },
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    db.add(asset)
                db.commit()
        except Exception:
            db.rollback()
            logger.warning("Failed to persist job assets in database", exc_info=True)
        finally:
            db.close()

        logger.info("Job completed", extra={"job_id": job_id, "result": result})
        return result
    except Exception as exc:
        error_message = f"Job finalization failed: {exc}\n{traceback.format_exc()}"
        logger.error("Finalization failed", extra={"job_id": job_id, "error": error_message})
        update_job_status(job_id, "failed", error=error_message)
        raise Ignore() from exc


@celery.task(bind=True, max_retries=3, name="worker.process_job")
def process_job(
    self,
    job_id: str,
    image_url: str,
    prompt: str,
    business_id: str,
    num_outputs: int = 1,
    preset_id: Optional[str] = None,
    use_case: Optional[str] = None,
    product_category: Optional[str] = None,
    brand_style: Optional[str] = None,
    output_format: Optional[str] = None,
    mode: Optional[str] = None,
    callback_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
):
    del metadata

    try:
        if correlation_id:
            os.environ["CORRELATION_ID"] = correlation_id

        log_event(
            LOGGER,
            event_type="processing_started",
            job_id=job_id,
            status="processing",
            business_id=business_id,
            num_outputs=num_outputs,
            preset_id=preset_id,
            use_case=use_case,
            product_category=product_category,
            brand_style=brand_style,
            output_format=output_format,
            mode=mode,
            correlation_id=correlation_id,
        )

        image_path = None
        try:
            styled_prompt = build_prompt(
                prompt,
                preset_id=preset_id,
                use_case=use_case,
                product_category=product_category,
                brand_style=brand_style,
            )
            output_spec = get_output_spec(output_format)
            inference_params = get_inference_params(preset_id, mode)

            image_path = download_input_image(job_id, image_url)
            processed_data = preprocess_image(job_id, image_path, output_spec)

            update_job_status(job_id, "processing", progress=70, step="generate")
            rendered_images = generate_images(
                processed_data,
                styled_prompt,
                inference_params,
                num_outputs,
            )

            upload_result = upload_results(
                job_id,
                rendered_images,
                business_id,
                output_spec.get("extension", "png"),
            )
            result = finalize_job(
                job_id,
                upload_result,
                output_spec=output_spec,
                actual_model=DEFAULT_MODEL_ID,
                inference_config_used=inference_params,
            )

            send_webhook(
                callback_url,
                {"job_id": job_id, "status": "completed", "images": upload_result},
                job_id,
            )

            log_event(
                LOGGER,
                event_type="completed",
                job_id=job_id,
                status="completed",
                correlation_id=correlation_id,
            )
            return result
        finally:
            try:
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
            except OSError:
                pass

    except requests.RequestException as exc:
        logger.warning("Retrying job after download failure", extra={"job_id": job_id})
        raise self.retry(exc=exc, countdown=5, max_retries=3) from exc
    except Ignore:
        logger.error("Job ignored due to error", extra={"job_id": job_id})
        send_webhook(callback_url, {"job_id": job_id, "status": "failed"}, job_id)
    except Exception as exc:
        error_message = f"Unhandled error in worker: {exc}"
        logger.error("Error processing job", extra={"job_id": job_id, "error": error_message})
        update_job_status(job_id, "failed", error=error_message)
        send_webhook(
            callback_url,
            {"job_id": job_id, "status": "failed", "error": error_message},
            job_id,
        )
        raise


process_job_sig = signature(process_job)
