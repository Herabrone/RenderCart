from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rendercart.admin import gpu_metrics
from rendercart.admin import router as admin_router
from rendercart.admin.gpu_metrics import parse_dcgm_metrics
from rendercart.auth import service as auth_service
from rendercart.auth.models import User
from rendercart.core.access import StaffRole


def sign_in(client: TestClient, db: Session, role: StaffRole, *, mfa: bool = True) -> None:
    user = User(email=f"{role.value}-{datetime.now(UTC).timestamp()}@example.com", staff_role=role)
    db.add(user)
    db.flush()
    token, _ = auth_service.create_session(db, user, "127.0.0.1", "gpu-tests", mfa)
    db.commit()
    client.cookies.set("rc_session", token)


def test_parse_dcgm_metrics_groups_values_by_gpu() -> None:
    rows = parse_dcgm_metrics(
        [
            '# HELP DCGM_FI_DEV_GPU_UTIL GPU utilization.',
            'DCGM_FI_DEV_GPU_UTIL{gpu="0",UUID="GPU-a",modelName="A100"} 73',
            'DCGM_FI_DEV_FB_USED{gpu="0",UUID="GPU-a",modelName="A100"} 12000',
            'DCGM_FI_DEV_GPU_TEMP{gpu="1",UUID="GPU-b",modelName="A100"} 65',
            'DCGM_FI_DEV_GPU_UTIL{gpu="bad"} NaN',
            'unrelated_metric{gpu="0"} 1',
        ]
    )

    assert rows == [
        {
            "device": "0",
            "name": "A100",
            "utilization_percent": 73.0,
            "memory_used_mib": 12000.0,
        },
        {"device": "1", "name": "A100", "temperature_celsius": 65.0},
    ]


def test_gpu_worker_snapshot_reports_only_gpu_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.closed = False

        def llen(self, queue: str) -> int:
            return {"gpu.image": 2, "gpu.audio": 3}.get(queue, 0)

        def close(self) -> None:
            self.closed = True

    fake_redis = FakeRedis()

    class FakeInspector:
        def active_queues(self) -> dict[str, list[dict[str, str]]] | None:
            return {
                "gpu-worker@host": [{"name": "gpu.image"}, {"name": "gpu.audio"}],
                "cpu-worker@host": [{"name": "cpu.default"}],
            }

    monkeypatch.setattr(
        gpu_metrics,
        "get_settings",
        lambda: type("Settings", (), {"celery_broker_url": None, "redis_url": "redis://broker/0"})(),
    )
    monkeypatch.setattr(
        gpu_metrics.Redis,
        "from_url",
        staticmethod(lambda *_args, **_kwargs: fake_redis),
    )
    monkeypatch.setattr(
        gpu_metrics.celery_app.control,
        "inspect",
        lambda **_kwargs: FakeInspector(),
    )

    snapshot = gpu_metrics._gpu_worker_snapshot()

    assert snapshot["status"] == "online"
    assert snapshot["workers_seen"] == 2
    assert snapshot["gpu_workers"] == ["gpu-worker@host"]
    assert snapshot["queue_depths"] == {
        "gpu.image": 2,
        "gpu.image.priority": 0,
        "gpu.audio": 3,
        "gpu.audio.priority": 0,
        "gpu.embed": 0,
    }
    assert snapshot["queue_depth_total"] == 5
    assert fake_redis.closed


@pytest.mark.parametrize(
    ("role", "mfa", "expected"),
    [
        (StaffRole.USER, True, 404),
        (StaffRole.ADMIN, False, 404),
        (StaffRole.ADMIN, True, 200),
        (StaffRole.SUPER_ADMIN, True, 200),
    ],
)
def test_gpu_health_is_mfa_gated_for_staff(
    client: TestClient,
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    role: StaffRole,
    mfa: bool,
    expected: int,
) -> None:
    sign_in(client, test_session, role, mfa=mfa)
    monkeypatch.setattr(
        admin_router,
        "gpu_health_snapshot",
        lambda: {"workers": {"status": "offline"}, "hardware": {"status": "unconfigured"}},
    )

    response = client.get("/api/admin/gpu")

    assert response.status_code == expected
    if expected == 200:
        assert response.json()["workers"]["status"] == "offline"
