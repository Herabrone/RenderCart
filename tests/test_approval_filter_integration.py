"""
Integration test for approval status filtering in assets endpoint.
"""
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_db
from api.main import app
from api.models_db import Asset, Base, Job


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


def test_assets_endpoint_approval_status_filter(monkeypatch):
    """Verify GET /assets?approval_status=approved returns only approved assets."""
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

            # Create assets with different approval statuses
            approved = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/approved.png",
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            pending = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/pending.png",
                approval_status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            rejected = Asset(
                job_id=job.id,
                asset_type="generated_output",
                asset_url="https://example.com/rejected.png",
                approval_status="rejected",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add_all([approved, pending, rejected])
            db.commit()

        # Filter by approved
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

        # Filter by rejected
        response = client.get(
            "/api/assets",
            headers={"X-API-Key": "business_1"},
            params={"approval_status": "rejected"},
        )
        assert response.status_code == 200
        assets = response.json().get("assets", [])
        assert len(assets) == 1
        assert assets[0]["approval_status"] == "rejected"
        assert assets[0]["asset_url"].endswith("rejected.png")

        # No filter returns all three
        response = client.get(
            "/api/assets",
            headers={"X-API-Key": "business_1"},
        )
        assert response.status_code == 200
        assets = response.json().get("assets", [])
        assert len(assets) == 3
        statuses = {a["approval_status"] for a in assets}
        assert statuses == {"approved", "pending", "rejected"}

    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_approval_stats_business_scoping(monkeypatch):
    """Verify approval stats respect business_id filter."""
    client, TestingSessionLocal, startup_handlers = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            job1 = Job(
                job_id="job-1",
                business_id="business_1",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            job2 = Job(
                job_id="job-2",
                business_id="business_2",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add_all([job1, job2])
            db.commit()
            db.refresh(job1)
            db.refresh(job2)

            # Business 1 has 2 approved, 1 pending
            Asset(
                job_id=job1.id,
                asset_type="generated_output",
                asset_url="https://example.com/b1-a1.png",
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            Asset(
                job_id=job1.id,
                asset_type="generated_output",
                asset_url="https://example.com/b1-a2.png",
                approval_status="approved",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            Asset(
                job_id=job1.id,
                asset_type="generated_output",
                asset_url="https://example.com/b1-p1.png",
                approval_status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            # Business 2 has 1 rejected
            Asset(
                job_id=job2.id,
                asset_type="generated_output",
                asset_url="https://example.com/b2-r1.png",
                approval_status="rejected",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.commit()

        # Get stats for business_1
        response = client.get(
            "/api/assets/approval-stats",
            headers={"X-API-Key": "business_1"},
        )
        assert response.status_code == 200
        stats = response.json().get("stats", {})
        assert stats.get("approved", 0) == 2
        assert stats.get("pending", 0) == 1
        assert stats.get("rejected", 0) == 0

        # Get stats for business_2
        response = client.get(
            "/api/assets/approval-stats",
            headers={"X-API-Key": "business_2"},
        )
        assert response.status_code == 200
        stats = response.json().get("stats", {})
        assert stats.get("approved", 0) == 0
        assert stats.get("pending", 0) == 0
        assert stats.get("rejected", 0) == 1

    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()
