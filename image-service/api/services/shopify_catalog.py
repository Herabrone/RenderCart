import structlog
import requests
from fastapi import HTTPException, status

from api.config import settings
from api.models_db import ShopifyStore
from api.services.shopify_crypto import decrypt_token

logger = structlog.get_logger(__name__)

_MAX_PRODUCT_FETCH = 250


def fetch_products(
    store: ShopifyStore,
    *,
    search: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Fetches products from a connected Shopify store for the publish selection UI.

    Returns a simplified list of product dicts — id, title, handle, primary image URL,
    variant count, and status.
    """
    limit = min(max(limit, 1), _MAX_PRODUCT_FETCH)
    token = decrypt_token(store.access_token_encrypted)

    params: dict = {
        "limit": limit,
        "fields": "id,title,handle,images,variants,status",
    }
    if search:
        params["title"] = search

    url = (
        f"https://{store.shop_domain}/admin/api"
        f"/{settings.shopify_api_version}/products.json"
    )
    try:
        response = requests.get(
            url,
            headers={"X-Shopify-Access-Token": token},
            params=params,
            timeout=settings.request_timeout_seconds,
        )
        if response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "Shopify access token is invalid or has been revoked. "
                    "Reconnect the store to continue."
                ),
            )
        response.raise_for_status()
    except HTTPException:
        raise
    except requests.RequestException as exc:
        logger.error("shopify_product_fetch_failed", shop=store.shop_domain, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch products from Shopify.",
        )

    products = response.json().get("products", [])
    return [_normalize_product(p) for p in products]


def _normalize_product(raw: dict) -> dict:
    images = raw.get("images") or []
    variants = raw.get("variants") or []
    return {
        "id": str(raw.get("id", "")),
        "title": raw.get("title", ""),
        "handle": raw.get("handle", ""),
        "status": raw.get("status", ""),
        "image_url": images[0].get("src") if images else None,
        "variant_count": len(variants),
    }
