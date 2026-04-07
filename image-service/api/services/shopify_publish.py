import time
from datetime import datetime

import requests
import structlog
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.models_db import Asset, ShopifyStore
from api.repositories import get_asset_for_business, get_shopify_store, mark_store_disconnected
from api.services.shopify_crypto import decrypt_token

logger = structlog.get_logger(__name__)

_MAX_429_RETRIES = 3


class ShopifyPublishError(Exception):
    pass


class ShopifyAuthError(ShopifyPublishError):
    """Raised when Shopify returns 401 — token revoked or expired."""
    pass


def _post_with_rate_limit_retry(url: str, headers: dict, json: dict, timeout: int) -> requests.Response:
    """Wraps a POST request with Shopify leaky-bucket rate limit handling.

    On 429 responses, reads the Retry-After header (defaulting to 2 s) and
    retries up to _MAX_429_RETRIES times before raising.
    """
    for attempt in range(_MAX_429_RETRIES + 1):
        resp = requests.post(url, headers=headers, json=json, timeout=timeout)
        if resp.status_code != 429:
            return resp
        if attempt == _MAX_429_RETRIES:
            break
        retry_after = float(resp.headers.get("Retry-After", "2"))
        logger.warning(
            "shopify_rate_limited",
            url=url,
            retry_after=retry_after,
            attempt=attempt + 1,
        )
        time.sleep(retry_after)

    raise ShopifyPublishError(
        f"Shopify API rate limit exceeded after {_MAX_429_RETRIES} retries. Try again shortly."
    )


def publish_asset_to_shopify(
    db: Session,
    asset: Asset,
    store_id: int,
    business_id: str,
    shopify_product_id: str,
    replace_existing_media: bool = False,
) -> None:
    """Executes the publish synchronously for the worker.
    
    Downloads the image from storage/URL and creates or replaces media on the
    Shopify product.
    Updates the Asset with status.
    """
    store = get_shopify_store(db, store_id, business_id)
    if not store or store.status != "active":
        raise ShopifyPublishError("Store is missing or disconnected. Reconnect to publish.")
    
    token = decrypt_token(store.access_token_encrypted)

    url = (
        f"https://{store.shop_domain}/admin/api/2024-01"
        f"/products/{shopify_product_id}/images.json"
    )
    payload = {
        "image": {
            "src": asset.asset_url
        }
    }

    try:
        resp = _post_with_rate_limit_retry(url, {"X-Shopify-Access-Token": token}, payload, timeout=60)

        if resp.status_code == 401:
            # Token has been revoked — mark store as disconnected in DB.
            mark_store_disconnected(db, store_id, reason="access_token_revoked")
            raise ShopifyAuthError(
                "Shopify access token has been revoked. Please reconnect the store."
            )

        if resp.status_code == 404:
            raise ShopifyPublishError(
                f"Product {shopify_product_id} was not found on store."
                " It may have been deleted."
            )

        resp.raise_for_status()
        data = resp.json()
        media_id = str(data.get("image", {}).get("id", ""))

        asset.shopify_publish_status = "succeeded"
        asset.shopify_media_id = media_id
        asset.shopify_product_id = shopify_product_id
        asset.shopify_error_message = None
        asset.shopify_published_at = datetime.utcnow()
        db.commit()
    except (ShopifyPublishError, ShopifyAuthError):
        raise
    except requests.RequestException as e:
        status_code = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
        error_text = getattr(e.response, "text", "") if hasattr(e, "response") else ""
        logger.error(
            "shopify_publish_failed",
            error=str(e),
            error_text=error_text,
            asset_id=asset.id,
            status=status_code,
        )
        raise ShopifyPublishError("Failed to upload image to Shopify API. " + str(e))

