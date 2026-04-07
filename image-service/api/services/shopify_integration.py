import hashlib
import hmac
import secrets
from datetime import datetime
from urllib.parse import urlencode

import requests
import structlog
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.config import settings
from api.models_db import ShopifyStore
from api.services.shopify_crypto import decrypt_token, encrypt_token

logger = structlog.get_logger(__name__)

_SHOPIFY_DOMAIN_SUFFIX = ".myshopify.com"


class ShopifyConfigError(Exception):
    pass


def _require_shopify_config() -> None:
    if not settings.shopify_api_key or not settings.shopify_api_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Shopify integration is not configured on this server.",
        )


def validate_shop_domain(shop_domain: str) -> str:
    """Validates and normalises a Shopify shop domain to the bare hostname."""
    domain = shop_domain.strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.rstrip("/")

    if not domain.endswith(_SHOPIFY_DOMAIN_SUFFIX):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"shop_domain must end with {_SHOPIFY_DOMAIN_SUFFIX}",
        )
    subdomain = domain[: -len(_SHOPIFY_DOMAIN_SUFFIX)]
    if not subdomain or "/" in subdomain or "." in subdomain:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="shop_domain must be in the format my-store.myshopify.com",
        )
    return domain


def build_oauth_url(shop_domain: str, business_id: str, redirect_uri: str) -> str:
    """Returns the Shopify OAuth authorization URL the merchant should visit."""
    _require_shopify_config()
    domain = validate_shop_domain(shop_domain)
    nonce = secrets.token_hex(16)
    state = f"{business_id}:{nonce}"
    params = {
        "client_id": settings.shopify_api_key,
        "scope": ",".join(settings.shopify_app_scopes),
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"https://{domain}/admin/oauth/authorize?{urlencode(params)}"


def verify_shopify_hmac(query_params: dict) -> bool:
    """Verifies the HMAC Shopify appends to OAuth callback query strings."""
    _require_shopify_config()
    received_hmac = query_params.get("hmac", "")
    sorted_params = "&".join(
        f"{k}={v}"
        for k, v in sorted(query_params.items())
        if k != "hmac"
    )
    expected = hmac.new(
        settings.shopify_api_secret.encode("utf-8"),
        sorted_params.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_hmac)


def extract_business_id_from_state(state: str) -> str:
    """Extracts the business_id encoded in the OAuth state parameter."""
    if not state or ":" not in state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter.",
        )
    return state.split(":", 1)[0]


def exchange_oauth_code(shop_domain: str, code: str) -> tuple[str, str]:
    """Exchanges an OAuth authorization code for a permanent access token.

    Returns a (access_token, scopes) tuple.
    """
    _require_shopify_config()
    url = f"https://{shop_domain}/admin/oauth/access_token"
    try:
        response = requests.post(
            url,
            json={
                "client_id": settings.shopify_api_key,
                "client_secret": settings.shopify_api_secret,
                "code": code,
            },
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("shopify_token_exchange_failed", shop=shop_domain, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to complete OAuth handshake with Shopify.",
        )

    data = response.json()
    token = data.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Shopify did not return an access token.",
        )
    scopes = data.get("scope", "")
    return token, scopes


def save_connected_store(
    db: Session,
    business_id: str,
    shop_domain: str,
    access_token: str,
    scopes: str | None = None,
) -> ShopifyStore:
    """Saves (or updates) a connected Shopify store for the given business."""
    from api.repositories import get_shopify_store_by_domain

    encrypted = encrypt_token(access_token)
    now = datetime.utcnow()

    existing = get_shopify_store_by_domain(db, shop_domain, business_id)
    if existing:
        existing.access_token_encrypted = encrypted
        existing.scopes = scopes
        existing.status = "active"
        existing.updated_at = now
        existing.error_details = None
        db.commit()
        db.refresh(existing)
        return existing

    store = ShopifyStore(
        business_id=business_id,
        shop_domain=shop_domain,
        access_token_encrypted=encrypted,
        scopes=scopes,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def disconnect_store(db: Session, store_id: int, business_id: str) -> bool:
    """Marks a store as disconnected. Returns True if found and updated."""
    from api.repositories import get_shopify_store

    store = get_shopify_store(db, store_id, business_id)
    if not store:
        return False
    store.status = "disconnected"
    store.updated_at = datetime.utcnow()
    db.commit()
    return True
