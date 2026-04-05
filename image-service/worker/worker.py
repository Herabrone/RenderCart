"""
Celery worker for image generation pipeline.
Processes jobs through a chain of tasks:
1. download_input_image
2. preprocess (rembg + resize)
3. generate_images (SDXL img2img)
4. upload_results (R2)
5. update_job_status
"""

import os
import time
import tempfile
import traceback
from io import BytesIO
from typing import List, Dict, Any
from datetime import datetime

import redis
import requests
from celery import Celery, signature
from celery.exceptions import Ignore, Retry
from kombu import Queue
from PIL import Image
import torch
from diffusers import StableDiffusionXLImg2ImgPipeline
from rembg import remove

from presets import apply_style_to_prompt, get_inference_params

# Initialize Celery
celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

# Configure Celery queues and routing
celery.conf.task_queues = (
    Queue("download"),
    Queue("preprocess"),
    Queue("generate"),
    Queue("upload"),
    Queue("status")
)

celery.conf.task_routes = {
    "worker.process_job": {"queue": "generate"},
    "tasks.download_input_image": {"queue": "download"},
    "tasks.preprocess_image": {"queue": "preprocess"},
    "tasks.generate_images": {"queue": "generate"},
    "tasks.upload_results": {"queue": "upload"},
    "tasks.update_job_status": {"queue": "status"}
}
celery.conf.task_default_queue = "generate"

# Redis connection for job tracking
redis_conn = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=os.getenv('REDIS_PASSWORD', ''),
    decode_responses=True
)

# Load SDXL pipeline (lazy initialization)
_sdxl_pipeline = None

def get_sdxl_pipeline():
    """Get or create SDXL pipeline with cache."""
    global _sdxl_pipeline
    if _sdxl_pipeline is None:
        print("Loading SDXL pipeline...")
        _sdxl_pipeline = StableDiffusionXLImg2ImgPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            variant="fp16",
            safety_checker=None
        ).to("cuda")
        print("SDXL pipeline loaded")
    return _sdxl_pipeline


def update_job_status(job_id: str, status: str, error: str = None, result: Dict[str, Any] = None):
    """
    Update job status in Redis.
    
    Args:
        job_id: Job ID
        status: Job status (pending, processing, completed, failed)
        error: Error message (if any)
        result: Result data (if completed)
    """
    job_data = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if error:
        job_data["error"] = error
    
    if result:
        job_data["result"] = result
    
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
        update_job_status(job_id, "processing", result={"step": "download"})
        
        print(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_file.write(response.content)
            tmp_path = tmp_file.name
        
        print(f"Image downloaded to {tmp_path}")
        return tmp_path
        
    except requests.RequestException as e:
        error_msg = f"Failed to download image: {str(e)}"
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
        update_job_status(job_id, "processing", result={"step": "preprocess"})
        
        print(f"Preprocessing image {image_path}")
        
        # Load image
        with open(image_path, "rb") as f:
            img_data = f.read()
        
        img = Image.open(BytesIO(img_data))
        
        # Remove background
        print("Removing background...")
        img = remove(img)
        
        # Convert to RGB and resize
        img = img.convert("RGB")
        img = img.resize((1024, 1024), Image.LANCZOS)
        
        # Save processed image to bytes
        output_buffer = BytesIO()
        img.save(output_buffer, format="PNG")
        processed_img_bytes = output_buffer.getvalue()
        
        print(f"Image preprocessed, size: {len(processed_img_bytes)} bytes")
        
        return {
            "image_bytes": processed_img_bytes,
            "style": style
        }
        
    except Exception as e:
        error_msg = f"Image preprocessing failed: {str(e)}\n{traceback.format_exc()}"
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
        update_job_status(job_id, "processing", result={"step": "generate"})
        
        print(f"Generating {num_images} image(s) with prompt: {prompt[:100]}...")
        
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
            print(f"Generated image {i+1}/{num_images}, size: {len(result_images[-1])} bytes")
        
        return result_images
        
    except Exception as e:
        error_msg = f"Image generation failed: {str(e)}\n{traceback.format_exc()}"
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
        update_job_status(job_id, "processing", result={"step": "upload"})
        
        print(f"Uploading {len(generated_images)} image(s) to R2")
        
        # In a real implementation, this would upload to R2
        # For now, we'll simulate it and return mock URLs
        r2_urls = []
        for i, img_bytes in enumerate(generated_images):
            # Simulate upload delay
            time.sleep(0.5)
            
            # Create mock URL
            mock_url = f"https://r2.example.com/{business_id}/jobs/{job_id}/image_{i+1}.png"
            r2_urls.append(mock_url)
            print(f"Uploaded image {i+1}: {mock_url}")
        
        return {
            "r2_urls": r2_urls,
            "count": len(r2_urls)
        }
        
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}\n{traceback.format_exc()}"
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


def finalize_job(job_id: str, upload_result: Dict[str, Any]):
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
        
        update_job_status(job_id, "completed", result=result)
        print(f"Job {job_id} completed successfully")
        
        return result
        
    except Exception as e:
        error_msg = f"Job finalization failed: {str(e)}\n{traceback.format_exc()}"
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


@celery.task(bind=True, max_retries=3, name="worker.process_job")
def process_job(self, job_id: str, image_url: str, prompt: str, style: str, business_id: str, num_outputs: int = 1):
    """
    Main task to process a job through the pipeline.
    
    Args:
        job_id: Job ID
        image_url: URL of input image
        prompt: User prompt
        style: Style name
        business_id: Business ID
        
    Returns:
        Final job result
    """
    try:
        # Apply style to prompt
        styled_prompt = apply_style_to_prompt(prompt, style)

        image_path = download_input_image(job_id, image_url)
        processed_data = preprocess_image(job_id, image_path, style)
        generated_images = generate_images(job_id, processed_data, styled_prompt, num_outputs)
        upload_result = upload_results(job_id, generated_images, business_id)
        result = finalize_job(job_id, upload_result)

        try:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
        except OSError:
            pass

        return result
        
    except Retry as e:
        raise self.retry(exc=e, countdown=e.countdown)
    except Ignore:
        print(f"Job {job_id} ignored due to error")
        raise
    except Exception as e:
        error_msg = f"Job processing failed: {str(e)}\n{traceback.format_exc()}"
        update_job_status(job_id, "failed", error=error_msg)
        raise Ignore()


# Task signatures for external use
process_job_sig = signature(process_job)
download_input_image_sig = signature(download_input_image)
preprocess_image_sig = signature(preprocess_image)
generate_images_sig = signature(generate_images)
upload_results_sig = signature(upload_results)
update_job_status_sig = signature(update_job_status)
