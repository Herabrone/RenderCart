from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.dependencies import get_db
from api.main import app
from api.models import JobResponse, JobStatus
from api.models_db import Base, BrandKit, Job


class FakeRedisStore:
    def __init__(self):
        self.jobs = {}
        self.business_ids = {}

    def create_job(self, job_id, business_id, request, **kwargs):
        snapshot = kwargs.get("brand_kit_snapshot")
        self.jobs[job_id] = JobResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            image_url=request.image_url,
            prompt=request.prompt,
            preset_id=request.preset_id,
            use_case=request.use_case,
            product_category=request.product_category,
            brand_style=request.brand_style,
            brand_kit_id=kwargs.get("brand_kit_id"),
            brand_kit_snapshot=snapshot,
            output_format=request.output_format,
            mode=request.mode,
            num_outputs=request.num_outputs,
            callback_url=request.callback_url,
            metadata=request.metadata or {},
            progress=0,
            step="queued",
        )
        self.business_ids[job_id] = business_id

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def get_job_business_id(self, job_id):
        return self.business_ids.get(job_id)


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

    fake_redis_store = FakeRedisStore()
    startup_handlers = list(app.router.on_startup)
    app.router.on_startup.clear()
    app.dependency_overrides[get_db] = override_get_db

    monkeypatch.setattr("api.app_state.api_auth.verify_api_key", lambda api_key: api_key)
    monkeypatch.setattr("api.main.usage_tracker.track_request", lambda *args, **kwargs: None)
    monkeypatch.setattr("api.services.generation.validate_public_http_url", lambda url, _field: url)
    monkeypatch.setattr("api.services.generation.celery.send_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("api.services.generation.redis_store", fake_redis_store)
    monkeypatch.setattr("api.routers.generation.redis_store", fake_redis_store)
    monkeypatch.setattr("api.routers.v1.redis_store", fake_redis_store)

    client = TestClient(app)
    return client, TestingSessionLocal, startup_handlers


def test_brand_kit_crud_and_business_scoping(monkeypatch):
    client, TestingSessionLocal, startup_handlers = _make_client(monkeypatch)
    try:
        create_response = client.post(
            "/api/brand-kits",
            headers={"X-API-Key": "business_1"},
            json={
                "name": "Flagship Store",
                "background": "warm cream sweep",
                "lighting": "soft side daylight",
                "tone": "clean and elevated",
                "framing": "centered hero composition",
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Flagship Store"

        list_response = client.get("/api/brand-kits", headers={"X-API-Key": "business_1"})
        assert list_response.status_code == 200
        assert len(list_response.json()["brand_kits"]) == 1

        update_response = client.patch(
            f"/api/brand-kits/{created['id']}",
            headers={"X-API-Key": "business_1"},
            json={"tone": "bold seasonal campaign"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["tone"] == "bold seasonal campaign"

        with TestingSessionLocal() as db:
            other_kit = BrandKit(
                business_id="business_2",
                name="Other Store",
                background="black paper",
                lighting="dramatic spot",
                tone="luxury",
                framing="off-center crop",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(other_kit)
            db.commit()
            db.refresh(other_kit)
            other_id = other_kit.id

        forbidden_response = client.get(
            f"/api/brand-kits/{other_id}",
            headers={"X-API-Key": "business_1"},
        )
        assert forbidden_response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()


def test_generate_persists_brand_kit_snapshot(monkeypatch):
    client, TestingSessionLocal, startup_handlers = _make_client(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            brand_kit = BrandKit(
                business_id="business_1",
                name="Core Catalog",
                background="neutral paper sweep",
                lighting="bright indirect daylight",
                tone="clean and modern",
                framing="tight hero crop",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(brand_kit)
            db.commit()
            db.refresh(brand_kit)
            brand_kit_id = brand_kit.id

        response = client.post(
            "/api/generate",
            headers={"X-API-Key": "business_1"},
            json={
                "image_url": "https://example.com/product.png",
                "prompt": "Ceramic mug for storefront launch",
                "brand_kit_id": brand_kit_id,
                "brand_kit_snapshot": {
                    "background": "neutral paper sweep",
                    "lighting": "bright indirect daylight",
                    "tone": "clean and modern",
                    "framing": "tight hero crop",
                },
            },
        )

        assert response.status_code == 202
        payload = response.json()
        assert payload["brand_kit_id"] == brand_kit_id
        assert payload["brand_kit_snapshot"]["name"] == "Core Catalog"
        assert payload["brand_style"] == (
            "background: neutral paper sweep, lighting: bright indirect daylight, "
            "tone: clean and modern, framing: tight hero crop"
        )

        with TestingSessionLocal() as db:
            job = db.query(Job).filter(Job.job_id == payload["job_id"]).first()
            assert job is not None
            assert job.brand_kit_id == brand_kit_id
            assert job.brand_kit_snapshot["name"] == "Core Catalog"
            assert job.brand_style == payload["brand_style"]
    finally:
        app.dependency_overrides.clear()
        app.router.on_startup[:] = startup_handlers
        client.close()
