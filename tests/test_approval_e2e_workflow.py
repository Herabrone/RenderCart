"""
End-to-end integration tests for the complete approval workflow.
Tests: generate → approve/reject → regenerate with asset filtering and stats.
"""
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_db
from api.main import app
from api.models_db import Asset, Base, Job


class FakeRedisStore:
    def __init__(self):
        self.jobs_stored = {}

    def create_job(self, job_id, business_id, request, **kwargs):
        self.jobs_stored[job_id] = {
            "job_id": job_id,
            "business_id": business_id,
            "prompt": request.prompt,
            "preset_id": request.preset_id,
            "image_url": request.image_url,
            "kwargs": kwargs,
        }

    def get_job(self, job_id):
        return None  # Simplified for test


class FakeCelery:
    def __init__(self):
        self.queued_tasks = []

    def send_task(self, name, args=None, kwargs=None, queue=None):
        self.queued_tasks.append((name, args, kwargs, queue))


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

    fake_redis = FakeRedisStore()
    fake_celery = FakeCelery()
    monkeypatch.setattr("api.services.generation.redis_store", fake_redis)
    monkeypatch.setattr("api.services.generation.celery", fake_celery)

    client = TestClient(app)
    return client, TestingSessionLocal, startup_handlers, fake_redis, fake_celery


def test_full_workflow_generate_approve_regenerate(monkeypatch):
    """Test complete: generate job → approve asset → regenerate."""
    client, TestingSessionLocal, startup_handlers, fake_redis, fake_celery = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            job = Job(
                job_id="job-workflow-1",
                business_id="merchant_1",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                image_url="https://example.com/product.png",
                prompt="professional product shot",
                preset_id="realvisxl_default",
                use_case="main_product_image",
                product_category="electronics",
                brand_style="modern minimalist",
                output_format="product_image",
                mode="production",
                num_outputs=2,
                job_metadata={"source": "api"},
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            asset1 = Asset(
                job_id=job.id,
                asset_type="generated_output",
                label="Candidate A",
                asset_url="https://example.com/candidate-a.png",
                approval_status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            asset2 = Asset(
                job_id=job.id,
                asset_type="generated_output",
                label="Candidate B",
                asset_url="https://example.com/candidate-b.png",
                approval_status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add_all([asset1, asset2])
            db.commit()
            db.refresh(asset1)
            db.refresh(asset2)

        approve_response = client.post(
            f"/api/assets/{asset1.id}/approve",
            headers={"X-API-Key": "merchant_1"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["approval_status"] == "approved"

        reject_response = client.post(
            f"/api/assets/{asset2.id}/reject",
            headers={"X-API-Key": "merchant_1"},
            json={"reason": "poor composition"},
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["approval_status"] == "rejected"
        assert reject_response.json()["rejection_reason"] == "poor composition"

        regen_response = client.post(
            f"/api/assets/{asset2.id}/regenerate",
            headers={"X-API-Key": "merchant_1"},
        )
        assert regen_response.status_code == 201
        assert regen_response.json()["source_asset_id"] == asset2.id

        with TestingSessionLocal() as db:
            stats = client.get(
                "/api/assets/approval-stats",
                headers={"X-API-Key": "merchant_1"},
            ).json()
            assert stats["stats"]["approved"] == 1
            assert stats["stats"]["rejected"] == 1
            assert stats["stats"]["pending"] >= 1

    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_gallery_filtering_by_approval_status(monkeypatch):
    """Test Gallery approval filtering works end-to-end."""
    client, TestingSessionLocal, startup_handlers, _fake_redis, _fake_celery = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            job = Job(
                job_id="job-gallery-1",
                business_id="merchant_2",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                image_url="https://example.com/src.png",
                prompt="test",
                preset_id="realvisxl_default",
                use_case="main_product_image",
                product_category="general",
                brand_style="clean",
                output_format="product_image",
                mode="production",
                num_outputs=1,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            for status in ["approved", "approved", "rejected", "pending"]:
                asset = Asset(
                    job_id=job.id,
                    asset_type="generated_output",
                    label=f"Asset {status}",
                    asset_url=f"https://example.com/{status}.png",
                    approval_status=status,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(asset)
            db.commit()

        approved_response = client.get(
            "/api/assets",
            headers={"X-API-Key": "merchant_2"},
            params={"approval_status": "approved"},
        )
        assert approved_response.status_code == 200
        approved_assets = approved_response.json()["assets"]
        assert len(approved_assets) == 2
        assert all(a["approval_status"] == "approved" for a in approved_assets)

        rejected_response = client.get(
            "/api/assets",
            headers={"X-API-Key": "merchant_2"},
            params={"approval_status": "rejected"},
        )
        assert rejected_response.status_code == 200
        rejected_assets = rejected_response.json()["assets"]
        assert len(rejected_assets) == 1

        pending_response = client.get(
            "/api/assets",
            headers={"X-API-Key": "merchant_2"},
            params={"approval_status": "pending"},
        )
        assert pending_response.status_code == 200
        pending_assets = pending_response.json()["assets"]
        assert len(pending_assets) == 1

    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_multi_output_job_comparison_and_selective_approval(monkeypatch):
    """Test multi-output job with selective approve/reject per variant."""
    client, TestingSessionLocal, startup_handlers, _fake_redis, _fake_celery = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            job = Job(
                job_id="job-multi-1",
                business_id="merchant_3",
                status="completed",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                image_url="https://example.com/product.png",
                prompt="vibrant lifestyle shot",
                preset_id="realvisxl_default",
                use_case="product_gallery_image",
                product_category="fashion",
                brand_style="trendy",
                output_format="product_gallery",
                mode="production",
                num_outputs=4,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

            assets = []
            for i in range(1, 5):
                asset = Asset(
                    job_id=job.id,
                    asset_type="generated_output",
                    label=f"Variant {i}",
                    asset_url=f"https://example.com/variant-{i}.png",
                    approval_status="pending",
                    output_index=i,
                    file_format="png",
                    width=1200,
                    height=1200,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(asset)
                assets.append(asset)
            db.commit()
            db.refresh(assets[0])
            db.refresh(assets[1])
            db.refresh(assets[2])
            db.refresh(assets[3])

        client.post(
            f"/api/assets/{assets[0].id}/approve",
            headers={"X-API-Key": "merchant_3"},
        )
        client.post(
            f"/api/assets/{assets[1].id}/approve",
            headers={"X-API-Key": "merchant_3"},
        )
        client.post(
            f"/api/assets/{assets[2].id}/reject",
            headers={"X-API-Key": "merchant_3"},
            json={"reason": "color cast"},
        )

        job_response = client.get(
            f"/api/jobs/job-multi-1",
            headers={"X-API-Key": "merchant_3"},
        )
        assert job_response.status_code == 200
        job_data = job_response.json()
        assert len(job_data["assets"]) == 4
        statuses = {a["approval_status"] for a in job_data["assets"]}
        assert "approved" in statuses
        assert "rejected" in statuses
        assert "pending" in statuses

    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()
