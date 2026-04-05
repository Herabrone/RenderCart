from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from celery.result import AsyncResult
import os
import time
import random
import uuid
from dotenv import load_dotenv
import redis
import logging

from models import GenerateRequest, JobResponse, JobStatus, RedisJobStore
from auth import APIKeyAuth
from storage import R2Storage
from usage import UsageTracker
from logging_config import setup_logging, generate_correlation_id, set_correlation_id, log_event

load_dotenv()

# Setup structured logging
logger = setup_logging()

app = FastAPI(
    title="RenderCart API",
    description="Product Context Image Generation Engine for RenderCart and Stockman integration.",
    version="1.0.0"
)

# API v1 Router for Stockman integration
from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1", tags=["v1"])

@v1_router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
async def v1_generate(
    request: GenerateRequest,
    business_id: str = Depends(APIKeyAuth().verify_api_key)
) -> dict:
    """Generate images via API v1 with optional webhook callback."""
    # Logic is identical for now but partitioned for versioning
    job_id = f"job_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Log job queued event
    log_event(
        logger,
        event_type="queued",
        job_id=job_id,
        status="pending",
        message="Job queued for processing",
        business_id=business_id,
        image_url=request.image_url,
        prompt=request.prompt,
        style=request.style.value,
        num_outputs=request.num_outputs
    )
    
    # Store in redis
    # Using existing redis_store from main.py context
    from models import RedisJobStore
    RedisJobStore().create_job(job_id, business_id, request)
    
    # Send to celery
    # Using existing celery from main.py context
    celery.send_task(
        "worker.process_job",
        args=[job_id, request.image_url, request.prompt, request.style.value, business_id, request.num_outputs],
        kwargs={"callback_url": request.callback_url}
    )
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job submitted successfully. Results will be sent to callback_url if provided."
    }

@v1_router.get("/job/{job_id}")
async def v1_get_job(
    job_id: str,
    business_id: str = Depends(APIKeyAuth().verify_api_key)
) -> JobResponse:
    """Get status of a specific generation job."""
    from models import RedisJobStore
    job = RedisJobStore().get_job(job_id)
    if not job or not job_id.startswith(f"job_{business_id}_"):
        raise HTTPException(status_code=404, detail="Job not found")
    return job

app.include_router(v1_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to generate and propagate correlation IDs
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Generate correlation ID and propagate through request headers."""
    correlation_id = request.headers.get("X-Correlation-ID") or generate_correlation_id()
    
    # Set correlation ID in environment for this request
    set_correlation_id(correlation_id)
    
    # Add to request state
    request.state.correlation_id = correlation_id
    
    # Log request with correlation ID
    log_event(
        logger,
        event_type="request",
        job_id=None,
        status="started",
        message=f"{request.method} {request.url.path}",
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method
    )
    
    response = await call_next(request)
    
    # Log response
    log_event(
        logger,
        event_type="response",
        job_id=None,
        status="completed",
        message=f"{request.method} {request.url.path} - {response.status_code}",
        correlation_id=correlation_id,
        status_code=response.status_code
    )
    
    return response

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
        
        # Log job queued event
        log_event(
            logger,
            event_type="queued",
            job_id=job_id,
            status="pending",
            message="Job queued for processing",
            business_id=business_id,
            image_url=request.image_url,
            prompt=request.prompt,
            style=request.style.value,
            num_outputs=request.num_outputs
        )
        
        # Send task to Celery
        celery.send_task(
            "worker.process_job",
            args=[job_id, request.image_url, request.prompt, request.style.value, business_id, request.num_outputs],
            kwargs={"callback_url": request.callback_url}
        )
        
        return {"job_id": job_id}
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logger,
            event_type="failed",
            job_id=None,
            status="error",
            message=f"Job submission failed: {str(e)}",
            error=str(e)
        )
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
        url = storage.upload_image(contents, filename)
        
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
