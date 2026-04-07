"""
Integration tests for Shopify store connect / catalog Phase 2 endpoints.

Uses an in-memory SQLite DB (same pattern as test_brand_kits_api.py) and
monkeypatches auth, external HTTP calls, and crypto so tests are fully
self-contained.
"""

import hashlib
import hmac
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_db
from api.main import app
from api.models_db import Base, ShopifyStore


# ---------------------------------------------------------------------------
# Shared test client factory
# ---------------------------------------------------------------------------


def _make_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("api.app_state.api_auth.verify_api_key", lambda key: key)
    monkeypatch.setenv("SHOPIFY_API_KEY", "test_api_key")
    monkeypatch.setenv("SHOPIFY_API_SECRET", "test_api_secret")
    monkeypatch.setenv("SHOPIFY_APP_HOST", "https://rendercart-test.example.com")
    monkeypatch.setenv("SHOPIFY_ENCRYPTION_KEY", "QWxpY2VBbGljZUFsaWNlQWxpY2VBbGljZUFsaWM=")

    # Reload settings so env patches take effect within the test process
    from api import config as cfg_module
    new_settings = cfg_module.load_settings()
    monkeypatch.setattr(cfg_module, "settings", new_settings)
    monkeypatch.setattr("api.routers.shopify.settings", new_settings)
    monkeypatch.setattr("api.services.shopify_integration.settings", new_settings)
    monkeypatch.setattr("api.services.shopify_catalog.settings", new_settings)
    monkeypatch.setattr("api.services.shopify_crypto.settings", new_settings)

    return TestClient(app), SessionLocal


# ---------------------------------------------------------------------------
# /shopify/oauth/start
# ---------------------------------------------------------------------------


def test_oauth_start_returns_authorization_url(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.get(
        "/api/shopify/oauth/start",
        params={"shop_domain": "mystore.myshopify.com"},
        headers={"X-API-Key": "business_1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "oauth_url" in data
    assert "mystore.myshopify.com" in data["oauth_url"]
    assert "client_id=test_api_key" in data["oauth_url"]
    assert data["shop_domain"] == "mystore.myshopify.com"


def test_oauth_start_rejects_invalid_domain(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.get(
        "/api/shopify/oauth/start",
        params={"shop_domain": "mystore.shopify.com"},
        headers={"X-API-Key": "business_1"},
    )
    assert response.status_code == 422


def test_oauth_start_strips_https_prefix(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.get(
        "/api/shopify/oauth/start",
        params={"shop_domain": "https://mystore.myshopify.com"},
        headers={"X-API-Key": "business_1"},
    )
    assert response.status_code == 200
    assert "mystore.myshopify.com" in response.json()["oauth_url"]


# ---------------------------------------------------------------------------
# /shopify/oauth/callback
# ---------------------------------------------------------------------------


def _build_callback_params(shop, code, state, secret="test_api_secret"):
    """Builds a valid Shopify HMAC-signed callback param dict."""
    params = {"shop": shop, "code": code, "state": state}
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(secret.encode(), sorted_params.encode(), hashlib.sha256).hexdigest()
    return {**params, "hmac": sig}


def test_oauth_callback_connects_store(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)

    with patch("api.services.shopify_integration.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "shppa_test_token", "scope": "write_products,read_products"},
            raise_for_status=lambda: None,
        )
        params = _build_callback_params(
            shop="mystore.myshopify.com",
            code="auth_code_123",
            state="business_1:nonce123",
        )
        response = client.get("/api/shopify/oauth/callback", params=params)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["store"]["shop_domain"] == "mystore.myshopify.com"
    assert data["store"]["business_id"] == "business_1"

    db = SessionLocal()
    store = db.query(ShopifyStore).filter(ShopifyStore.business_id == "business_1").first()
    assert store is not None
    assert store.status == "active"
    assert store.access_token_encrypted != "shppa_test_token"  # must be encrypted


def test_oauth_callback_rejects_bad_hmac(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.get(
        "/api/shopify/oauth/callback",
        params={
            "shop": "mystore.myshopify.com",
            "code": "code",
            "state": "business_1:nonce",
            "hmac": "badhmacsignature",
        },
    )
    assert response.status_code == 400


def test_oauth_callback_reconnect_updates_existing_store(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)

    with patch("api.services.shopify_integration.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "shppa_first_token", "scope": "write_products"},
            raise_for_status=lambda: None,
        )
        params = _build_callback_params("mystore.myshopify.com", "code1", "business_1:nonce1")
        client.get("/api/shopify/oauth/callback", params=params)

    with patch("api.services.shopify_integration.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "shppa_new_token", "scope": "write_products,read_products"},
            raise_for_status=lambda: None,
        )
        params = _build_callback_params("mystore.myshopify.com", "code2", "business_1:nonce2")
        client.get("/api/shopify/oauth/callback", params=params)

    db = SessionLocal()
    stores = db.query(ShopifyStore).filter(ShopifyStore.business_id == "business_1").all()
    assert len(stores) == 1  # upsert, not duplicate


# ---------------------------------------------------------------------------
# /shopify/stores  and  /shopify/stores/{id}
# ---------------------------------------------------------------------------


def _seed_store(SessionLocal, business_id="business_1", shop_domain="mystore.myshopify.com"):
    from api.services.shopify_crypto import encrypt_token
    db = SessionLocal()
    store = ShopifyStore(
        business_id=business_id,
        shop_domain=shop_domain,
        access_token_encrypted=encrypt_token("shppa_test"),
        scopes="write_products",
        status="active",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    db.close()
    return store.id


def test_list_stores_returns_connected_stores(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    _seed_store(SessionLocal)

    response = client.get("/api/shopify/stores", headers={"X-API-Key": "business_1"})
    assert response.status_code == 200
    stores = response.json()["stores"]
    assert len(stores) == 1
    assert stores[0]["shop_domain"] == "mystore.myshopify.com"


def test_list_stores_is_business_scoped(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    _seed_store(SessionLocal, business_id="business_1")
    _seed_store(SessionLocal, business_id="business_2", shop_domain="other.myshopify.com")

    response = client.get("/api/shopify/stores", headers={"X-API-Key": "business_1"})
    stores = response.json()["stores"]
    assert all(s["business_id"] == "business_1" for s in stores)


def test_disconnect_store(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    store_id = _seed_store(SessionLocal)

    response = client.delete(
        f"/api/shopify/stores/{store_id}",
        headers={"X-API-Key": "business_1"},
    )
    assert response.status_code == 200

    db = SessionLocal()
    store = db.query(ShopifyStore).filter(ShopifyStore.id == store_id).first()
    assert store.status == "disconnected"


def test_disconnect_store_not_found(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.delete("/api/shopify/stores/9999", headers={"X-API-Key": "business_1"})
    assert response.status_code == 404


def test_disconnect_store_business_isolation(monkeypatch):
    """A business cannot disconnect another business's store."""
    client, SessionLocal = _make_client(monkeypatch)
    store_id = _seed_store(SessionLocal, business_id="business_2")

    response = client.delete(
        f"/api/shopify/stores/{store_id}",
        headers={"X-API-Key": "business_1"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /shopify/stores/{id}/products
# ---------------------------------------------------------------------------


def test_fetch_products_returns_normalized_list(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    store_id = _seed_store(SessionLocal)

    with patch("api.services.shopify_catalog.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "products": [
                    {
                        "id": 123456,
                        "title": "Wooden Chair",
                        "handle": "wooden-chair",
                        "status": "active",
                        "images": [{"src": "https://cdn.shopify.com/chair.jpg"}],
                        "variants": [{"id": 1}, {"id": 2}],
                    }
                ]
            },
            raise_for_status=lambda: None,
        )
        response = client.get(
            f"/api/shopify/stores/{store_id}/products",
            headers={"X-API-Key": "business_1"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["store_id"] == store_id
    products = data["products"]
    assert len(products) == 1
    assert products[0]["id"] == "123456"
    assert products[0]["title"] == "Wooden Chair"
    assert products[0]["variant_count"] == 2
    assert products[0]["image_url"] == "https://cdn.shopify.com/chair.jpg"


def test_fetch_products_passes_search_to_shopify(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    store_id = _seed_store(SessionLocal)

    with patch("api.services.shopify_catalog.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"products": []},
            raise_for_status=lambda: None,
        )
        client.get(
            f"/api/shopify/stores/{store_id}/products?search=chair",
            headers={"X-API-Key": "business_1"},
        )
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["title"] == "chair"


def test_fetch_products_404_for_unknown_store(monkeypatch):
    client, _ = _make_client(monkeypatch)

    response = client.get("/api/shopify/stores/9999/products", headers={"X-API-Key": "business_1"})
    assert response.status_code == 404


def test_fetch_products_409_for_disconnected_store(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    store_id = _seed_store(SessionLocal)

    db = SessionLocal()
    store = db.query(ShopifyStore).filter(ShopifyStore.id == store_id).first()
    store.status = "disconnected"
    db.commit()
    db.close()

    response = client.get(
        f"/api/shopify/stores/{store_id}/products",
        headers={"X-API-Key": "business_1"},
    )
    assert response.status_code == 409


def test_fetch_products_401_from_shopify_raises_http_401(monkeypatch):
    client, SessionLocal = _make_client(monkeypatch)
    store_id = _seed_store(SessionLocal)

    with patch("api.services.shopify_catalog.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401, raise_for_status=lambda: None)
        response = client.get(
            f"/api/shopify/stores/{store_id}/products",
            headers={"X-API-Key": "business_1"},
        )
    assert response.status_code == 401
