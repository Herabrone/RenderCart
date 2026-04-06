from enum import Enum
from pydantic import BaseModel
from typing import List, Optional
import redis
from datetime import datetime

from config import settings

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
    callback_url: Optional[str] = None
    
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
    result_urls: Optional[List[str]] = None
    progress: Optional[int] = None
    step: Optional[str] = None
    error: Optional[str] = None

class RedisJobStore:
    """Store job metadata in Redis hashes"""
    
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
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
            'result_urls': '',
            'progress': '0',
            'step': '',
            'error': ''
        })
    
    def get_job(self, job_id: str) -> Optional[JobResponse]:
        """Get job details from Redis"""
        key = f"job:{job_id}"
        data = self.redis.hgetall(key)
        
        if not data:
            return None
        
        # Build output_urls for backward compatibility
        output_urls = None
        if data.get('output_urls'):
            output_urls = [url for url in data['output_urls'].split(',') if url]
        
        # Build result_urls from new field or fallback to output_urls
        result_urls = None
        if data.get('result_urls'):
            result_urls = [url for url in data['result_urls'].split(',') if url]
        elif output_urls:
            result_urls = output_urls
        
        return JobResponse(
            job_id=job_id,
            status=JobStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            output_urls=output_urls,
            result_urls=result_urls,
            progress=int(data['progress']) if data.get('progress') else None,
            step=data['step'] if data.get('step') else None,
            error=data['error'] if data['error'] else None
        )
    
    def update_job_status(self, job_id: str, status: JobStatus, output_urls: Optional[List[str]] = None, result_urls: Optional[List[str]] = None, progress: Optional[int] = None, step: Optional[str] = None, error: Optional[str] = None) -> None:
        """Update job status and metadata"""
        key = f"job:{job_id}"
        update_data = {
            'status': status.value,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if output_urls is not None:
            update_data['output_urls'] = ','.join(output_urls)
        
        if result_urls is not None:
            update_data['result_urls'] = ','.join(result_urls)
        
        if progress is not None:
            update_data['progress'] = str(progress)
        
        if step is not None:
            update_data['step'] = step
        
        if error is not None:
            update_data['error'] = error
        
        self.redis.hset(key, mapping=update_data)
