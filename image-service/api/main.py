from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from celery import Celery
from celery.result import AsyncResult
import os
import time
import random
from dotenv import load_dotenv

from models import GenerateRequest, JobResponse, JobStatus, RedisJobStore
from auth import APIKeyAuth
from storage import R2Storage

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

# Celery configuration
celery = Celery(
    "tasks",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

@app.get("/")
def root():
    return {"status": "running"}

@app.post("/generate")
async def generate_image(
    request: GenerateRequest,
    business_id: str = Depends(api_auth.verify_api_key_dependency)
) -> dict:
    """Generate images from input image and prompt"""
    try:
        # Create job record
        job_id = f"job_{business_id}_{int(time.time())}_{random.randint(1000, 9999)}"
        redis_store.create_job(job_id, business_id, request)
        
        # Send task to Celery
        task = celery.send_task(
            "worker.generate_image",
            args=[job_id, request.image_url, request.prompt, request.style.value, request.num_outputs]
        )
        
        return {"job_id": job_id}
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
    if job.job_id.startswith(f"job_{business_id}_"):
        return job
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

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
