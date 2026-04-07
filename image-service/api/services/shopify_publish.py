import json
from datetime import datetime

import requests
import structlog
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.models_db import Asset
from api.repositories import get_asset_for_business, get_shopify_store
from api.services.shopify_crypto import decrypt_token

logger = structlog.get_logger(__name__)


class ShopifyPublishError(Exception):
    pass


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
    
    # In a real system, you'd fetch the bytes from R2 or passed URL and upload 
    # to Shopify using the graphql `productCreateMedia` or `productCreateImage`.
    # For now, we simulate the GraphQL request by posting JSON to the REST/GraphQL endpoint.
    
    # We will use the REST API here for simplicity if the asset is already a public URL.
    # Otherwise, you need to stage it to Shopify's StagedUpload URL.
    # Assuming pre-signed asset url or public url is accessible by Shopify:
    import urllib.parse
    
    url = f"https://{store.shop_domain}/admin/api/2024-01/products/{shopify_product_id}/images.json"
    payload = {
        "image": {
            "src": asset.asset_url
        }
    }
    
    try:
        if replace_existing_media:
            # We would first delete existing media or just add via REST and let user sort it out
            # For v1 replacement MVP (without fetching all images and matching), 
            # we simply add a new image. A robust replace would use GraphQL productCreateMedia 
            # and delete media mutations.
            # Simplified: Add new.
            pass
            
        resp = requests.post(url, headers={"X-Shopify-Access-Token": token}, json=payload, timeout=60)
        
        # If 404, product doesn't exist.
        if resp.status_code == 404:
            raise ShopifyPublishError(f"Product {shopify_product_id} not found on store.")
        
        resp.raise_for_status()
        data = resp.json()
        media_id = str(data.get("image", {}).get("id", ""))
        
        asset.shopify_publish_status = "published"
        asset.shopify_media_id = media_id
        asset.shopify_product_id = shopify_product_id
        asset.shopify_error_message = None
        asset.shopify_published_at = datetime.utcnow()
        db.commit()
    except requests.RequestException as e:
        status_code = getattr(e.response, "status_code", None) if hasattr(e, "response") else None
        error_text = getattr(e.response, "text", "") if hasattr(e, "response") else ""
        logger.error("shopify_publish_failed", error=str(e), error_text=error_text, asset_id=asset.id, status=status_code)
        raise ShopifyPublishError("Failed to upload image to Shopify API. " + str(e))

