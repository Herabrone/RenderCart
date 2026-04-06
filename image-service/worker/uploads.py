import logging
from typing import Any, Dict, List

from api.storage import R2Storage

from worker.status_store import update_job_status

logger = logging.getLogger("rendercart.worker")
storage = R2Storage()


def upload_results(
    job_id: str,
    generated_images: List[bytes],
    business_id: str,
    output_extension: str = "png",
) -> Dict[str, Any]:
    update_job_status(job_id, "processing", progress=90, step="upload")
    logger.info("Uploading images", extra={"job_id": job_id, "count": len(generated_images)})

    items = []
    for index, image_bytes in enumerate(generated_images, start=1):
        object_key = f"{business_id}/jobs/{job_id}/image_{index}.{output_extension}"
        upload_result = storage.upload_bytes(
            image_bytes,
            object_key,
            content_type="image/png" if output_extension == "png" else "image/jpeg",
        )
        items.append(upload_result)

    return {
        "items": items,
        "r2_urls": [item["url"] for item in items],
        "storage_keys": [item["storage_key"] for item in items],
        "count": len(items),
    }
