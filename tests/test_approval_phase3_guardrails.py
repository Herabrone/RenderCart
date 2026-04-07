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
        self.created_jobs = []

    def create_job(self, job_id, business_id, request, **kwargs):
        self.created_jobs.append(
            {
                "job_id": job_id,
                "business_id": business_id,
                "request": request,
                "kwargs": kwargs,
            }
        )


class FakeCelery:
    def __init__(self):
        self.tasks = []

    def send_task(self, name, args=None, kwargs=None, queue=None):
        self.tasks.append(
            {
                "name": name,
                "args": args or [],
                "kwargs": kwargs or {},
                "queue": queue,
            }
        )


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


def _create_job_and_asset(db, *, business_id: str, status: str = "pending"):
    job = Job(
        job_id=f"job-{business_id}",
        business_id=business_id,
        status="completed",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        image_url="https://example.com/source.png",
        prompt="improve composition",
        preset_id="realvisxl_default",
        use_case="main_product_image",
        product_category="general",
        brand_style="clean",
        output_format="product_image",
        mode="production",
        num_outputs=1,
        callback_url="https://example.com/webhook",
        job_metadata={"origin": "test"},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    asset = Asset(
        job_id=job.id,
        asset_type="generated_output",
        label="Candidate",
        asset_url="https://example.com/asset.png",
        approval_status=status,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return job, asset


def test_ownership_guardrail_on_approve_and_reject(monkeypatch):
    client, TestingSessionLocal, startup_handlers, _fake_redis, _fake_celery = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            _job, asset = _create_job_and_asset(db, business_id="business_2", status="pending")

        approve_response = client.post(
            f"/api/assets/{asset.id}/approve",
            headers={"X-API-Key": "business_1"},
        )
        assert approve_response.status_code == 404

        reject_response = client.post(
            f"/api/assets/{asset.id}/reject",
            headers={"X-API-Key": "business_1"},
            json={"reason": "blurry"},
        )
        assert reject_response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_status_transition_guardrails(monkeypatch):
    client, TestingSessionLocal, startup_handlers, _fake_redis, _fake_celery = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            _job, asset = _create_job_and_asset(db, business_id="business_1", status="pending")

        approve_response = client.post(
            f"/api/assets/{asset.id}/approve",
            headers={"X-API-Key": "business_1"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["approval_status"] == "approved"

        reapprove_response = client.post(
            f"/api/assets/{asset.id}/approve",
            headers={"X-API-Key": "business_1"},
        )
        assert reapprove_response.status_code == 400

        reject_after_approve_response = client.post(
            f"/api/assets/{asset.id}/reject",
            headers={"X-API-Key": "business_1"},
            json={"reason": "bad tone"},
        )
        assert reject_after_approve_response.status_code == 400
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_regenerate_includes_provenance_and_requeues(monkeypatch):
    client, TestingSessionLocal, startup_handlers, fake_redis, fake_celery = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            source_job, asset = _create_job_and_asset(db, business_id="business_1", status="approved")

        regenerate_response = client.post(
            f"/api/assets/{asset.id}/regenerate",
            headers={"X-API-Key": "business_1"},
        )

        assert regenerate_response.status_code == 201
        payload = regenerate_response.json()
        assert payload["source_asset_id"] == asset.id
        assert payload["source_job_id"] == source_job.job_id
        assert payload["new_job_id"].startswith("job_business_1_")

        with TestingSessionLocal() as db:
            new_job = db.query(Job).filter(Job.job_id == payload["new_job_id"]).first()
            assert new_job is not None
            assert new_job.business_id == "business_1"
            assert new_job.prompt == source_job.prompt
            assert new_job.output_format == source_job.output_format
            assert new_job.job_metadata is not None
            assert new_job.job_metadata["regenerated_from"]["source_asset_id"] == asset.id
            assert new_job.job_metadata["regenerated_from"]["source_job_id"] == source_job.job_id

        assert len(fake_redis.created_jobs) == 1
        assert fake_redis.created_jobs[0]["business_id"] == "business_1"

        assert len(fake_celery.tasks) == 1
        assert fake_celery.tasks[0]["name"] == "worker.process_job"
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()
