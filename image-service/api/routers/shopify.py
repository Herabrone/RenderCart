from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from api.app_state import api_auth
from api.config import settings
from api.dependencies import get_db
from api.models import (
    ShopifyPublishRequest,
    ShopifyPublishResponse,
    ShopifyBulkPublishRequest,
    ShopifyBulkPublishResponse,
)
from api.repositories import get_asset_for_business, get_shopify_store, list_shopify_stores
from api.serializers import shopify_store_to_dict
from api.services import shopify_catalog, shopify_integration
from worker.shopify_worker import publish_to_shopify, bulk_publish_to_shopify

router = APIRouter(tags=["shopify"])


@router.post("/shopify/oauth/start", status_code=status.HTTP_200_OK)
def shopify_oauth_start(
    shop_domain: str = Query(..., description="The merchant's .myshopify.com domain"),
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    request: Request = None,
):
    """Returns the Shopify OAuth authorization URL for the merchant to visit.

    The front end should redirect the merchant's browser to the returned oauth_url.
    """
    if not settings.shopify_app_host:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SHOPIFY_APP_HOST is not configured.",
        )
    redirect_uri = f"{settings.shopify_app_host.rstrip('/')}/api/shopify/oauth/callback"
    domain = shopify_integration.validate_shop_domain(shop_domain)
    oauth_url = shopify_integration.build_oauth_url(domain, business_id, redirect_uri)
    return {"oauth_url": oauth_url, "shop_domain": domain}


@router.get("/shopify/oauth/callback")
def shopify_oauth_callback(
    shop: str = Query(...),
    code: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    db: Session = Depends(get_db),
):
    """OAuth callback endpoint — Shopify redirects here after merchant approval.

    Verifies the Shopify HMAC, exchanges the code for an access token, and
    persists the connected store record.
    """
    query_params = {"shop": shop, "code": code, "state": state, "hmac": hmac}
    if not shopify_integration.verify_shopify_hmac(query_params):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Shopify callback signature.",
        )

    business_id = shopify_integration.extract_business_id_from_state(state)
    shop_domain = shopify_integration.validate_shop_domain(shop)
    access_token, scopes = shopify_integration.exchange_oauth_code(shop_domain, code)
    store = shopify_integration.save_connected_store(
        db, business_id, shop_domain, access_token, scopes
    )
    return {"status": "connected", "store": shopify_store_to_dict(store)}


@router.get("/shopify/stores")
def get_shopify_stores(
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    """Lists all Shopify stores connected to this business account."""
    stores = list_shopify_stores(db, business_id)
    return {"stores": [shopify_store_to_dict(s) for s in stores]}


@router.delete("/shopify/stores/{store_id}", status_code=status.HTTP_200_OK)
def disconnect_shopify_store(
    store_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    """Disconnects a Shopify store from this business account."""
    found = shopify_integration.disconnect_store(db, store_id, business_id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found.")
    return {"status": "disconnected", "store_id": store_id}


@router.get("/shopify/stores/{store_id}/products")
def get_shopify_products(
    store_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, description="Filter products by title"),
    limit: int = Query(default=50, ge=1, le=250),
):
    """Returns products from the given connected Shopify store.

    Products are fetched from the Shopify API on demand — no local cache.
    Only stores in 'active' status can be queried.
    """
    store = get_shopify_store(db, store_id, business_id)
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found.")
    if store.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Store is not active. Reconnect the store before fetching products.",
        )

    products = shopify_catalog.fetch_products(store, search=search, limit=limit)
    return {
        "store_id": store_id,
        "shop_domain": store.shop_domain,
        "products": products,
    }


@router.post("/assets/{asset_id}/publish/shopify", status_code=status.HTTP_202_ACCEPTED)
def request_shopify_publish(
    asset_id: int,
    request: ShopifyPublishRequest,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    """Submits an async task to publish an approved asset to Shopify."""
    asset = get_asset_for_business(db, asset_id, business_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    if asset.approval_status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Asset must be approved before publishing to Shopify.",
        )

    store = get_shopify_store(db, request.store_id, business_id)
    if not store or store.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Store is missing or disconnected. Reconnect to publish.",
        )

    asset.shopify_publish_status = "pending"
    asset.shopify_error_message = None
    db.commit()

    # Trigger Celery task
    publish_to_shopify.delay(
        asset_id,
        business_id,
        request.store_id,
        request.shopify_product_id,
        request.replace_existing_media,
    )

    return {
        "asset_id": asset_id,
        "shopify_publish_status": asset.shopify_publish_status
    }


@router.get("/assets/{asset_id}/publish-status", status_code=status.HTTP_200_OK)
def get_shopify_publish_status(
    asset_id: int,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    """Retrieve the Shopify publish status of an asset."""
    asset = get_asset_for_business(db, asset_id, business_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return {
        "asset_id": asset_id,
        "shopify_publish_status": asset.shopify_publish_status,
        "shopify_product_id": asset.shopify_product_id,
        "shopify_media_id": asset.shopify_media_id,
        "shopify_error_message": asset.shopify_error_message,
        "shopify_published_at": asset.shopify_published_at.isoformat() if asset.shopify_published_at else None,
    }


@router.post("/assets/bulk-publish/shopify", status_code=status.HTTP_202_ACCEPTED)
def bulk_publish_assets_to_shopify(
    request: ShopifyBulkPublishRequest,
    business_id: str = Depends(api_auth.verify_api_key_dependency),
    db: Session = Depends(get_db),
):
    """Queues async publish tasks for multiple approved assets to one Shopify store.

    Returns two lists: queued (will be published) and skipped (not approved or
    not owned by this business).
    """
    store = get_shopify_store(db, request.store_id, business_id)
    if not store or store.status != "active":
        raise HTTPException(
            status_code=400,
            detail="Store is missing or disconnected. Reconnect to publish.",
        )

    queued: list[int] = []
    skipped: list[int] = []

    for item in request.items:
        asset = get_asset_for_business(db, item.asset_id, business_id)
        if not asset or asset.approval_status != "approved":
            skipped.append(item.asset_id)
            continue

        asset.shopify_publish_status = "pending"
        asset.shopify_error_message = None
        queued.append(item.asset_id)

    if queued:
        db.commit()
        task_items = [
            {
                "asset_id": item.asset_id,
                "store_id": request.store_id,
                "shopify_product_id": item.shopify_product_id,
                "replace_existing_media": item.replace_existing_media,
            }
            for item in request.items
            if item.asset_id in queued
        ]
        bulk_publish_to_shopify.apply_async(
            args=[task_items, business_id],
            queue="shopify_publish",
        )

    return {
        "store_id": request.store_id,
        "queued": queued,
        "skipped": skipped,
    }

