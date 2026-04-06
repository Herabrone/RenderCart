"""Celery worker for image generation pipeline."""

import os
import random
import tempfile
import traceback
import logging
from io import BytesIO
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
import requests
import torch
import boto3
from botocore.client import Config
from celery import Celery, signature
from celery.exceptions import Ignore
from diffusers import StableDiffusionXLImg2ImgPipeline
from kombu import Queue
from PIL import Image
from rembg import remove

from logging_config import log_event, setup_logging
from model_loader import get_default_pipeline, DEFAULT_MODEL_ID
from business_presets import build_prompt, get_inference_params, get_output_spec

LOGGER = setup_logging()
logger = logging.getLogger("rendercart.worker")

celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
)

celery.conf.task_queues = (
    Queue("download"),
    Queue("preprocess"),
    Queue("generate"),
    Queue("upload"),
    Queue("status"),
)

celery.conf.task_routes = {
    "worker.process_job": {"queue": "generate"},
    "tasks.download_input_image": {"queue": "download"},
    "tasks.preprocess_image": {"queue": "preprocess"},
    "tasks.generate_images": {"queue": "generate"},
    "tasks.upload_results": {"queue": "upload"},
    "tasks.update_job_status": {"queue": "status"},
}
celery.conf.task_default_queue = "generate"

redis_conn = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", ""),
    decode_responses=True,
)

_generation_pipeline: Optional[StableDiffusionXLImg2ImgPipeline] = None


def check_gpu_availability() -> bool:
    """Run quick CUDA checks and emit diagnostics."""
    try:
        if not torch.cuda.is_available():
            logger.error("CUDA unavailable for worker")
            return False

        device_index = 0
        device_name = torch.cuda.get_device_name(device_index)
        total_mem_gb = torch.cuda.get_device_properties(device_index).total_memory / (1024 ** 3)
        free_mem_bytes, _ = torch.cuda.mem_get_info(device_index)
        free_mem_gb = free_mem_bytes / (1024 ** 3)

        log_event(
            LOGGER,
            event_type="gpu_preflight",
            status="ok",
            message="CUDA preflight checks passed",
            gpu_name=device_name,
            total_gb=round(total_mem_gb, 2),
            free_gb=round(free_mem_gb, 2),
        )

        if free_mem_gb < 2:
            logger.warning("Low available GPU memory", extra={"free_gb": round(free_mem_gb, 2)})
        return True
    except Exception as exc:
        logger.error("GPU preflight check failed", extra={"error": str(exc)})
        return False


def get_sdxl_pipeline() -> StableDiffusionXLImg2ImgPipeline:
    """Create pipeline lazily once per worker process."""
    global _generation_pipeline
    if _generation_pipeline is None:
        if not check_gpu_availability():
            raise RuntimeError("GPU preflight check failed. CUDA device is required for generation.")
        logger.info("Loading default generation pipeline")
        _generation_pipeline = get_default_pipeline()
    return _generation_pipeline


def update_job_status(
    job_id: str,
    status: str,
    progress: Optional[int] = None,
    step: Optional[str] = None,
    result_urls: Optional[List[str]] = None,
    error: Optional[str] = None,
):
    """
    Update job status in Redis with consistent fields.
    
    Args:
        job_id: Job ID
        status: Job status (pending, processing, completed, failed)
        progress: Progress percentage (0-100)
        step: Current processing step (download, preprocess, generate, upload)
        result_urls: List of result URLs
        error: Error message (if any)
    """
    logger.info(
        "Updating job status",
        extra={"job_id": job_id, "status": status, "progress": progress, "step": step},
    )
    
    job_data = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if progress is not None:
        job_data["progress"] = str(progress)
    
    if step is not None:
        job_data["step"] = step
    
    if result_urls is not None:
        job_data["result_urls"] = ",".join(result_urls)
        # Maintain backward compatibility with output_urls
        job_data["output_urls"] = ",".join(result_urls)
    
    if error is not None:
        job_data["error"] = error
    
    redis_conn.hset(f"job:{job_id}", mapping=job_data)


def download_input_image(job_id: str, image_url: str) -> str:
    """
    Download input image from URL and save to temporary file.
    
    Args:
        job_id: Job ID
        image_url: URL of the input image
        
    Returns:
        Path to temporary image file
        
    Raises:
        requests.RequestException: If download fails
    """
    try:
        update_job_status(job_id, "processing", progress=10, step="download")
        
        logger.info("Downloading image", extra={"job_id": job_id, "image_url": image_url})
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        logger.info("Image downloaded", extra={"job_id": job_id, "image_path": tmp_path})
        return tmp_path
        
    except requests.RequestException as e:
        error_msg = f"Failed to download image: {str(e)}"
        logger.error("Download failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise


def preprocess_image(job_id: str, image_path: str, output_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Preprocess image: remove background and resize to the requested output format.
    
    Args:
        job_id: Job ID
        image_path: Path to input image
        output_spec: Output format specification
    
    Returns:
        Dictionary with processed image bytes and output spec
    
    Raises:
        Ignore: If image processing fails
    """
    try:
        update_job_status(job_id, "processing", progress=40, step="preprocess")

        logger.info("Preprocessing image", extra={"job_id": job_id, "image_path": image_path})

        # Load image
        with open(image_path, "rb") as f:
            img_data = f.read()

        img = Image.open(BytesIO(img_data))

        # Remove background
        logger.debug("Removing background", extra={"job_id": job_id})
        img = remove(img)

        # Convert to RGB and resize to output aspect ratio
        img = img.convert("RGB")
        img = img.resize((output_spec["width"], output_spec["height"]), Image.LANCZOS)

        # Save processed image to bytes
        output_buffer = BytesIO()
        img.save(output_buffer, format="PNG")
        processed_img_bytes = output_buffer.getvalue()

        logger.info("Image preprocessed", extra={"job_id": job_id, "size": len(processed_img_bytes), "output_spec": output_spec})

        return {
            "image_bytes": processed_img_bytes,
            "output_spec": output_spec
        }

    except Exception as e:
        error_msg = f"Image preprocessing failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Preprocessing failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


def generate_images(job_id: str, processed_data: Dict[str, Any], prompt: str, inference_params: Dict[str, Any], num_images: int = 1) -> List[bytes]:
    """
    Generate images using the configured pipeline.
    
    Args:
        job_id: Job ID
        processed_data: Dictionary with image_bytes and output spec
        prompt: User prompt with business-styled guidance
        inference_params: Inference parameters resolved from preset and mode
        num_images: Number of images to generate
        
    Returns:
        List of generated image bytes
        
    Raises:
        Ignore: If generation fails
    """
    try:
        update_job_status(job_id, "processing", progress=70, step="generate")

        logger.info("Generating images", extra={"job_id": job_id, "num_images": num_images, "prompt": prompt[:100], "inference_params": inference_params})

        img = Image.open(BytesIO(processed_data["image_bytes"]))
        pipeline = get_sdxl_pipeline()

        generator = torch.Generator(device="cpu").manual_seed(random.randint(0, 2**32 - 1))
        images = pipeline(
            prompt=prompt,
            image=img,
            num_images_per_prompt=num_images,
            **inference_params,
            generator=generator
        ).images

        output_format = processed_data.get("output_spec", {}).get("extension", "png").upper()
        if output_format == "JPG":
            output_format = "JPEG"

        result_images = []
        for i, img in enumerate(images):
            output_buffer = BytesIO()
            img.save(output_buffer, format=output_format)
            result_images.append(output_buffer.getvalue())
            logger.info("Generated image", extra={"job_id": job_id, "image_number": i+1, "size": len(result_images[-1]), "format": output_format})

        return result_images

    except Exception as e:
        error_msg = f"Image generation failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Generation failed: %s", error_msg)
        update_job_status(job_id, "failed", error=error_msg)
        torch.cuda.empty_cache()
        raise Ignore()


def upload_results(job_id: str, generated_images: List[bytes], business_id: str, output_extension: str = "png") -> Dict[str, Any]:
    """
    Upload generated images to R2 storage.
    
    Args:
        job_id: Job ID
        generated_images: List of image bytes
        business_id: Business ID for storage path
        output_extension: File extension for uploaded images
        
    Returns:
        Dictionary with R2 URLs
        
    Raises:
        Ignore: If upload fails
    """
    try:
        update_job_status(job_id, "processing", progress=90, step="upload")
        
        logger.info("Uploading images", extra={"job_id": job_id, "count": len(generated_images), "output_extension": output_extension})

        endpoint = os.getenv("R2_ENDPOINT")
        access_key = os.getenv("R2_ACCESS_KEY_ID")
        secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
        bucket_name = os.getenv("R2_BUCKET_NAME")

        if not endpoint or not access_key or not secret_key or not bucket_name:
            raise RuntimeError("Missing required R2 configuration in environment variables")

        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

        r2_urls = []
        for i, img_bytes in enumerate(generated_images):
            object_key = f"{business_id}/jobs/{job_id}/image_{i+1}.{output_extension}"

            s3_client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=img_bytes,
                ContentType="image/png" if output_extension == "png" else "image/jpeg",
            )

            url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket_name, "Key": object_key},
                ExpiresIn=3600,
            )
            r2_urls.append(url)
            logger.info("Image uploaded", extra={"job_id": job_id, "image_number": i+1, "object_key": object_key})
        
        return {
            "r2_urls": r2_urls,
            "count": len(r2_urls)
        }
        
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Upload failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


def finalize_job(job_id: str, upload_result: Dict[str, Any], actual_model: Optional[str] = None, inference_config_used: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Finalize job and update status to completed.
    
    Args:
        job_id: Job ID
        upload_result: Result from upload task
        actual_model: Model identifier used for generation
        inference_config_used: Actual inference parameters applied
        
    Returns:
        Final job result
    """
    try:
        result = {
            "status": "completed",
            "r2_urls": upload_result.get("r2_urls", []),
            "image_count": upload_result.get("count", 0),
            "completed_at": datetime.utcnow().isoformat()
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
        logger.info("Job completed", extra={"job_id": job_id, "result": result})

        return result
        
    except Exception as e:
        error_msg = f"Job finalization failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Finalization failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


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
    """
    Main task to process a job through the pipeline.
    
    Args:
        job_id: Job ID
        image_url: URL of input image
        prompt: User prompt
        business_id: Business ID
        num_outputs: Number of generated images
        preset_id: Preset identifier for generation
        use_case: Business use case
        product_category: Product category
        brand_style: Brand style descriptor
        output_format: Desired output format
        mode: Generation mode (preview/production)
        callback_url: Optional URL to send webhook results
        metadata: Optional metadata dictionary
    """
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

        styled_prompt = build_prompt(
            prompt,
            preset_id=preset_id,
            use_case=use_case,
            product_category=product_category,
            brand_style=brand_style,
        )
        logger.debug("Built business prompt", extra={"job_id": job_id, "prompt": styled_prompt[:120]})

        output_spec = get_output_spec(output_format)
        inference_params = get_inference_params(preset_id, mode)

        image_path = download_input_image(job_id, image_url)
        processed_data = preprocess_image(job_id, image_path, output_spec)
        generated_images = generate_images(job_id, processed_data, styled_prompt, inference_params, num_outputs)
        upload_result = upload_results(job_id, generated_images, business_id, output_spec.get("extension", "png"))
        result = finalize_job(job_id, upload_result, actual_model=DEFAULT_MODEL_ID, inference_config_used=inference_params)

        if callback_url:
            try:
                logger.info("Sending webhook", extra={"job_id": job_id, "callback_url": callback_url})
                payload = {
                    "job_id": job_id,
                    "status": "completed",
                    "images": upload_result,
                }
                requests.post(callback_url, json=payload, timeout=10)
                logger.info("Webhook sent successfully", extra={"job_id": job_id})
            except Exception as e:
                logger.error("Failed to send webhook", extra={"job_id": job_id, "callback_url": callback_url, "error": str(e)})

        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
        except OSError:
            pass

        log_event(
            LOGGER,
            event_type="completed",
            job_id=job_id,
            status="completed",
            correlation_id=correlation_id,
        )
        return result

    except requests.RequestException as e:
        logger.warning("Retrying job after download failure", extra={"job_id": job_id})
        raise self.retry(exc=e, countdown=5, max_retries=3)
    except Ignore:
        logger.error("Job ignored due to error", extra={"job_id": job_id})
        if callback_url:
            try:
                requests.post(callback_url, json={"job_id": job_id, "status": "failed"}, timeout=10)
            except:
                pass
    except Exception as e:
        error_msg = f"Unhandled error in worker: {str(e)}"
        logger.error("Error processing job", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        if callback_url:
            try:
                requests.post(callback_url, json={"job_id": job_id, "status": "failed", "error": error_msg}, timeout=10)
            except:
                pass
        raise e


# Task signatures for external use
process_job_sig = signature(process_job)
download_input_image_sig = signature(download_input_image)
preprocess_image_sig = signature(preprocess_image)
generate_images_sig = signature(generate_images)
upload_results_sig = signature(upload_results)
update_job_status_sig = signature(update_job_status)
