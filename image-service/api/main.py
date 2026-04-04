from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from celery.result import AsyncResult
import os
import time
import random
from dotenv import load_dotenv
import redis

from models import GenerateRequest, JobResponse, JobStatus, RedisJobStore
from auth import APIKeyAuth
from storage import R2Storage
from usage import UsageTracker

load_dotenv()

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
redis_store = RedisJobStore()
storage = R2Storage()
api_auth = APIKeyAuth()
usage_tracker = UsageTracker()

# Redis connection for rate limiting
rate_limit_redis = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', '6379')),
    password=os.getenv('REDIS_PASSWORD', ''),
    decode_responses=True
)

# Celery configuration
celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

@app.get("/")
def root():
    return {"status": "running"}

@app.get("/rate_limit/{business_id}")
def get_rate_limit_status(business_id: str):
    """Get current rate limit status for a business"""
    key = f"rate_limit:{business_id}"
    current = rate_limit_redis.get(key)
    return {
        "business_id": business_id,
        "current_requests": int(current) if current else 0,
        "limit": 10,
        "reset_time": "1 minute"
    }

async def check_rate_limit(business_id: str):
    """Check and update rate limit for business"""
    key = f"rate_limit:{business_id}"
    pipeline = rate_limit_redis.pipeline()
    
    # Increment request count
    pipeline.incr(key)
    # Set expiration to 1 minute
    pipeline.expire(key, 60)
    
    # Get current count
    current = rate_limit_redis.get(key)
    
    if int(current) if current else 0 > 10:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 10 requests per minute."
        )

@app.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def generate_image(
    request: GenerateRequest,
    business_id: str = Depends(api_auth.verify_api_key_dependency)
) -> dict:
    """Generate images from input image and prompt"""
    try:
        # Check rate limit
        await check_rate_limit(business_id)
        
        # Create job record
        job_id = f"job_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"
        redis_store.create_job(job_id, business_id, request)
        
        # Send task to Celery
        task = celery.send_task(
            "worker.generate_image",
            args=[job_id, request.image_url, request.prompt, request.style.value, request.num_outputs]
        )
        
        return {"job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/job/{job_id}")
async def get_job_status(
    job_id: str,
    business_id: str = Depends(api_auth.verify_api_key_dependency)
) -> JobResponse:
    """Get job status and results"""
    job = redis_store.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    
    # Verify business ownership
    if not job.job_id.startswith(f"job_{business_id}_"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return job

@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "redis": "connected",
            "r2": "configured"
        }
    }


@app.get("/usage")
async def get_usage(business_id: str, days: int = 7):
    """Get API usage statistics for a business"""
    try:
        stats = usage_tracker.get_usage_stats(business_id, days)
        return stats
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    business_id: str = Depends(api_auth.verify_api_key_dependency)
) -> dict:
    """Upload an image to R2 storage"""
    try:
        # Check rate limit
        await check_rate_limit(business_id)
        
        # Read file content
        contents = await file.read()
        
        # Generate unique filename
        timestamp = int(time.time())
        filename = f"{business_id}_{timestamp}_{file.filename}"
        
        # Upload to R2
        url = storage.upload_file(contents, filename)
        
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
