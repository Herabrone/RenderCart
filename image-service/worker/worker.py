"""Celery worker for image generation pipeline."""

import os
import time
import tempfile
import traceback
import logging
from io import BytesIO
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
import requests
import torch
from celery import Celery, signature
from celery.exceptions import Ignore, Retry
from diffusers import StableDiffusionXLImg2ImgPipeline
from kombu import Queue
from PIL import Image
from rembg import remove

from logging_config import log_event, setup_logging
from presets import apply_style_to_prompt, get_inference_params

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

_sdxl_pipeline: Optional[StableDiffusionXLImg2ImgPipeline] = None


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
    global _sdxl_pipeline
    if _sdxl_pipeline is None:
        if not check_gpu_availability():
            raise RuntimeError("GPU preflight check failed. CUDA device is required for generation.")
        logger.info("Loading SDXL pipeline")
        _sdxl_pipeline = StableDiffusionXLImg2ImgPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            variant="fp16",
            safety_checker=None,
        ).to("cuda")
        logger.info("SDXL pipeline loaded")
    return _sdxl_pipeline


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
        Retry: If download fails (retries 3 times)
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
        raise Retry(exc=e, countdown=5)


def preprocess_image(job_id: str, image_path: str, style: str) -> Dict[str, Any]:
    """
    Preprocess image: remove background and resize to 1024x1024.
    
    Args:
        job_id: Job ID
        image_path: Path to input image
        style: Style name for prompt formatting
        
    Returns:
        Dictionary with processed image bytes and style info
        
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
        
        # Convert to RGB and resize
        img = img.convert("RGB")
        img = img.resize((1024, 1024), Image.LANCZOS)
        
        # Save processed image to bytes
        output_buffer = BytesIO()
        img.save(output_buffer, format="PNG")
        processed_img_bytes = output_buffer.getvalue()
        
        logger.info("Image preprocessed", extra={"job_id": job_id, "size": len(processed_img_bytes)})
        
        return {
            "image_bytes": processed_img_bytes,
            "style": style
        }
        
    except Exception as e:
        error_msg = f"Image preprocessing failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Preprocessing failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


def generate_images(job_id: str, processed_data: Dict[str, Any], prompt: str, num_images: int = 1) -> List[bytes]:
    """
    Generate images using SDXL img2img.
    
    Args:
        job_id: Job ID
        processed_data: Dictionary with image_bytes and style
        prompt: User prompt with style applied
        num_images: Number of images to generate
        
    Returns:
        List of generated image bytes
        
    Raises:
        Ignore: If generation fails
    """
    try:
        update_job_status(job_id, "processing", progress=70, step="generate")
        
        logger.info("Generating images", extra={"job_id": job_id, "num_images": num_images, "prompt": prompt[:100]})
        
        # Get inference parameters from style
        style = processed_data["style"]
        inference_params = get_inference_params(style)
        
        # Load and prepare image
        img = Image.open(BytesIO(processed_data["image_bytes"]))
        
        # Get pipeline
        pipeline = get_sdxl_pipeline()
        
        # Generate images
        generator = torch.Generator(device="cuda").manual_seed(42)
        images = pipeline(
            prompt=prompt,
            image=img,
            num_images_per_prompt=num_images,
            **inference_params,
            generator=generator
        ).images
        
        # Convert to bytes
        result_images = []
        for i, img in enumerate(images):
            output_buffer = BytesIO()
            img.save(output_buffer, format="PNG")
            result_images.append(output_buffer.getvalue())
            logger.info("Generated image", extra={"job_id": job_id, "image_number": i+1, "size": len(result_images[-1])})
        
        return result_images
        
    except Exception as e:
        error_msg = f"Image generation failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Generation failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


def upload_results(job_id: str, generated_images: List[bytes], business_id: str) -> Dict[str, Any]:
    """
    Upload generated images to R2 storage.
    
    Args:
        job_id: Job ID
        generated_images: List of image bytes
        business_id: Business ID for storage path
        
    Returns:
        Dictionary with R2 URLs
        
    Raises:
        Ignore: If upload fails
    """
    try:
        update_job_status(job_id, "processing", progress=90, step="upload")
        
        logger.info("Uploading images", extra={"job_id": job_id, "count": len(generated_images)})
        
        # In a real implementation, this would upload to R2
        # For now, we'll simulate it and return mock URLs
        r2_urls = []
        for i, img_bytes in enumerate(generated_images):
            # Simulate upload delay
            time.sleep(0.5)
            
            # Create mock URL
            mock_url = f"https://r2.example.com/{business_id}/jobs/{job_id}/image_{i+1}.png"
            r2_urls.append(mock_url)
            logger.info("Image uploaded", extra={"job_id": job_id, "image_number": i+1, "url": mock_url})
        
        return {
            "r2_urls": r2_urls,
            "count": len(r2_urls)
        }
        
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}\n{traceback.format_exc()}"
        logger.error("Upload failed", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


def finalize_job(job_id: str, upload_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Finalize job and update status to completed.
    
    Args:
        job_id: Job ID
        upload_result: Result from upload task
        
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
    style: str,
    business_id: str,
    num_outputs: int = 1,
    callback_url: Optional[str] = None,
    correlation_id: Optional[str] = None,
):
    """
    Main task to process a job through the pipeline.
    
    Args:
        job_id: Job ID
        image_url: URL of input image
        prompt: User prompt
        style: Style name
        business_id: Business ID
        num_outputs: Number of generated images
        callback_url: Optional URL to send webhook results
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
            correlation_id=correlation_id,
        )
        
        # Apply style to prompt
        styled_prompt = apply_style_to_prompt(prompt, style)
        logger.debug("Applied style to prompt", extra={"job_id": job_id, "style": style})

        image_path = download_input_image(job_id, image_url)
        processed_data = preprocess_image(job_id, image_path, style)
        generated_images = generate_images(job_id, processed_data, styled_prompt, num_outputs)
        upload_result = upload_results(job_id, generated_images, business_id)
        result = finalize_job(job_id, upload_result)

        # Send webhook if callback_url is provided
        if callback_url:
            try:
                logger.info("Sending webhook", extra={"job_id": job_id, "callback_url": callback_url})
                payload = {
                    "job_id": job_id,
                    "status": "completed",
                    "images": upload_result
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

    except Retry as e:
        logger.warning("Retrying job", extra={"job_id": job_id, "countdown": e.countdown})
        raise self.retry(exc=e, countdown=e.countdown)
    except Ignore:
        logger.error("Job ignored due to error", extra={"job_id": job_id})
        # Notify of failure if callback is set
        if callback_url:
            try:
                requests.post(callback_url, json={"job_id": job_id, "status": "failed"}, timeout=10)
            except:
                pass
    except Exception as e:
        error_msg = f"Unhandled error in worker: {str(e)}"
        logger.error("Error processing job", extra={"job_id": job_id, "error": error_msg})
        update_job_status(job_id, "failed", error=error_msg)
        # Notify of failure if callback is set
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
