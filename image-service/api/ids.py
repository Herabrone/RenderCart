import re
import uuid


def _sanitize_business_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()) or "business"


def generate_job_id(business_id: str) -> str:
    return f"job_{_sanitize_business_id(business_id)}_{uuid.uuid4().hex}"


def generate_batch_id(business_id: str) -> str:
    return f"batch_{_sanitize_business_id(business_id)}_{uuid.uuid4().hex}"
