from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from api.app_state import api_auth
from api.config import settings
from api.dependencies import get_db
from api.repositories import get_shopify_store, list_shopify_stores
from api.serializers import shopify_store_to_dict
from api.services import shopify_catalog, shopify_integration

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
