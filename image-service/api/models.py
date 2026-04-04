from enum import Enum
from pydantic import BaseModel
from typing import List, Optional
import redis
import os
from datetime import datetime

class ImageStyle(str, Enum):
    """Supported image generation styles"""
    REALISTIC = "realistic"
    CARTOON = "cartoon"
    ANIME = "anime"
    WATERCOLOR = "watercolor"
    SKETCH = "sketch"

class GenerateRequest(BaseModel):
    """Request model for image generation"""
    image_url: str
    prompt: str
    style: ImageStyle
    num_outputs: int = 1
    
    def __init__(self, **data):
        super().__init__(**data)
        if not 1 <= self.num_outputs <= 4:
            raise ValueError("num_outputs must be between 1 and 4")

class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobResponse(BaseModel):
    """Response model for job status"""
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    output_urls: Optional[List[str]] = None
    error: Optional[str] = None

class RedisJobStore:
    """Store job metadata in Redis hashes"""
    
    def __init__(self):
        self.redis = redis.Redis(
            host=os.getenv('REDIS_HOST', 'redis'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD', ''),
            decode_responses=True
        )
    
    def create_job(self, job_id: str, business_id: str, request: GenerateRequest) -> None:
        """Create a new job in Redis"""
        key = f"job:{job_id}"
        self.redis.hset(key, mapping={
            'business_id': business_id,
            'status': JobStatus.PENDING.value,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'image_url': request.image_url,
            'prompt': request.prompt,
            'style': request.style.value,
            'num_outputs': str(request.num_outputs),
            'output_urls': '',
            'error': ''
        })
    
    def get_job(self, job_id: str) -> Optional[JobResponse]:
        """Get job details from Redis"""
        key = f"job:{job_id}"
        data = self.redis.hgetall(key)
        
        if not data:
            return None
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            output_urls=[url for url in data['output_urls'].split(',') if url] if data['output_urls'] else None,
            error=data['error'] if data['error'] else None
        )
    
    def update_job_status(self, job_id: str, status: JobStatus, output_urls: Optional[List[str]] = None, error: Optional[str] = None) -> None:
        """Update job status and metadata"""
        key = f"job:{job_id}"
        update_data = {
            'status': status.value,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if output_urls is not None:
            update_data['output_urls'] = ','.join(output_urls)
        
        if error is not None:
            update_data['error'] = error
        
        self.redis.hset(key, mapping=update_data)
