import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis
from api.db import SessionLocal
from api.models_db import Job

logger = logging.getLogger("rendercart.worker")
redis_conn = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", ""),
    decode_responses=True,
)


def persist_job_status(
    job_id: str,
    *,
    status: Optional[str] = None,
    progress: Optional[int] = None,
    step: Optional[str] = None,
    actual_model: Optional[str] = None,
    inference_config_used: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return
        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if step is not None:
            job.step = step
        if actual_model is not None:
            job.actual_model = actual_model
        if inference_config_used is not None:
            job.inference_config_used = inference_config_used
        if error is not None:
            job.error = error
        job.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        logger.warning("Failed to persist job status to database", exc_info=True)
    finally:
        db.close()


def update_job_status(
    job_id: str,
    status: str,
    *,
    progress: Optional[int] = None,
    step: Optional[str] = None,
    result_urls: Optional[List[str]] = None,
    error: Optional[str] = None,
    actual_model: Optional[str] = None,
    inference_config_used: Optional[Dict[str, Any]] = None,
) -> None:
    logger.info(
        "Updating job status",
        extra={"job_id": job_id, "status": status, "progress": progress, "step": step},
    )

    payload = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if progress is not None:
        payload["progress"] = str(progress)
    if step is not None:
        payload["step"] = step
    if result_urls is not None:
        joined = ",".join(result_urls)
        payload["result_urls"] = joined
        payload["output_urls"] = joined
    if error is not None:
        payload["error"] = error
    if actual_model is not None:
        payload["actual_model"] = actual_model
    if inference_config_used is not None:
        payload["inference_config_used"] = json.dumps(inference_config_used)

    redis_conn.hset(f"job:{job_id}", mapping=payload)
    persist_job_status(
        job_id,
        status=status,
        progress=progress,
        step=step,
        actual_model=actual_model,
        inference_config_used=inference_config_used,
        error=error,
    )
