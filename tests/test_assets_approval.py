from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_db
from api.main import app
from api.models_db import Asset, Base, Job
from api.services.approval import get_assets_by_approval_status


def _make_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    startup_handlers = list(app.router.on_startup)
    app.router.on_startup.clear()
    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr("api.app_state.api_auth.verify_api_key", lambda api_key: api_key)
    monkeypatch.setattr("api.main.usage_tracker.track_request", lambda *args, **kwargs: None)

    client = TestClient(app)
    return client, TestingSessionLocal, startup_handlers


def test_get_assets_by_approval_status_filters_by_business(monkeypatch):
    client, TestingSessionLocal, startup_handlers = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            job = Job(
                job_id="job-1",
                business_id="business_1",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            approved_asset = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/approved.png",
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            rejected_asset = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/rejected.png",
                approval_status="rejected",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add_all([approved_asset, rejected_asset])
            db.commit()

            filtered = get_assets_by_approval_status(db, status="approved", business_id="business_1")

        assert len(filtered) == 1
        assert filtered[0].approval_status == "approved"
        assert filtered[0].asset_url.endswith("approved.png")
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_assets_endpoint_supports_approval_status_filter(monkeypatch):
    client, TestingSessionLocal, startup_handlers = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            job = Job(
                job_id="job-2",
                business_id="business_1",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            pending_asset = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/pending.png",
                approval_status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            approved_asset = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/approved.png",
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add_all([pending_asset, approved_asset])
            db.commit()

        response = client.get(
            "/api/assets",
            headers={"X-API-Key": "business_1"},
            params={"approval_status": "approved"},
        )

        assert response.status_code == 200
        assets = response.json().get("assets", [])
        assert len(assets) == 1
        assert assets[0]["approval_status"] == "approved"
        assert assets[0]["asset_url"].endswith("approved.png")
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()
