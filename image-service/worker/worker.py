import os
import time
from celery import Celery
from PIL import Image
import requests
import redis
from dotenv import load_dotenv

load_dotenv()

# Initialize Celery
celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

# Initialize Redis for job metadata
redis_conn = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    password=os.getenv('REDIS_PASSWORD', ''),
    decode_responses=True
)

@celery.task(name="worker.generate_image")
def generate_image(job_id: str, image_url: str, prompt: str, style: str, num_outputs: int) -> dict:
    """Generate images using AI models"""
    
    # Update job status to processing
    redis_conn.hset(f"job:{job_id}", "status", "processing")
    redis_conn.hset(f"job:{job_id}", "updated_at", time.strftime('%Y-%m-%dT%H:%M:%S'))
    
    try:
        # Simulate image generation (placeholder for actual AI model)
        time.sleep(5)  # Simulate processing time
        
        # For now, just create a placeholder image
        img = Image.new('RGB', (512, 512), color='lightblue')
        
        # Save to bytes
        output_bytes = []
        for i in range(num_outputs):
            img.save(f'/tmp/output_{i}.png', 'PNG')
            with open(f'/tmp/output_{i}.png', 'rb') as f:
                output_bytes.append(f.read())
        
        # Return success
        result = {
            'status': 'completed',
            'output_count': num_outputs,
            'message': 'Image generation completed successfully'
        }
        
        return result
        
    except Exception as e:
        # Update job status to failed
        redis_conn.hset(f"job:{job_id}", "status", "failed")
        redis_conn.hset(f"job:{job_id}", "error", str(e))
        redis_conn.hset(f"job:{job_id}", "updated_at", time.strftime('%Y-%m-%dT%H:%M:%S'))
        
        raise
