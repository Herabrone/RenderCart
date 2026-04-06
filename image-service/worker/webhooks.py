import logging

import requests
from config import settings
from url_safety import validate_public_http_url

logger = logging.getLogger("rendercart.worker")


def send_webhook(callback_url: str | None, payload: dict, job_id: str) -> None:
    if not callback_url:
        return

    try:
        validate_public_http_url(callback_url, "callback_url")
        requests.post(callback_url, json=payload, timeout=settings.callback_timeout_seconds)
        logger.info(
            "Webhook sent successfully",
            extra={"job_id": job_id, "callback_url": callback_url},
        )
    except Exception as exc:
        logger.error(
            "Failed to send webhook",
            extra={"job_id": job_id, "callback_url": callback_url, "error": str(exc)},
        )
