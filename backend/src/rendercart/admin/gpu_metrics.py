"""Private GPU worker and exporter health for the admin dashboard."""

import re
from collections.abc import Iterable
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from celery.app.control import Inspect
from redis import Redis

from rendercart.core.config import get_settings
from rendercart.jobs.celery_app import app as celery_app

_GPU_QUEUES = (
    "gpu.image",
    "gpu.image.priority",
    "gpu.audio",
    "gpu.audio.priority",
    "gpu.embed",
)
_METRIC_NAMES = {
    "DCGM_FI_DEV_GPU_UTIL": "utilization_percent",
    "DCGM_FI_DEV_MEM_COPY_UTIL": "memory_utilization_percent",
    "DCGM_FI_DEV_FB_USED": "memory_used_mib",
    "DCGM_FI_DEV_FB_FREE": "memory_free_mib",
    "DCGM_FI_DEV_GPU_TEMP": "temperature_celsius",
    "DCGM_FI_DEV_POWER_USAGE": "power_watts",
}
_SAMPLE = re.compile(
    r"^(?P<name>DCGM_FI_DEV_[A-Z0-9_]+)\{(?P<labels>[^}]*)\}\s+(?P<value>-?[0-9]+(?:\.[0-9]+)?)$"
)
_LABEL = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)="((?:\\.|[^"\\])*)"')


def _gpu_worker_snapshot() -> dict[str, object]:
    settings = get_settings()
    broker_url = settings.celery_broker_url or settings.redis_url.rsplit("/", 1)[0] + "/1"
    redis_client = Redis.from_url(broker_url, socket_connect_timeout=1, socket_timeout=1)
    inspect: Inspect = celery_app.control.inspect(timeout=0.8)
    try:
        active_queues = inspect.active_queues() or {}
        worker_names = sorted(active_queues)
        gpu_workers = sorted(
            name
            for name, queues in active_queues.items()
            if any(
                queue.get("name") in _GPU_QUEUES
                for queue in queues
                if isinstance(queue, dict)
            )
        )
        depths = {
            queue: int(cast(int, redis_client.llen(queue)))
            for queue in _GPU_QUEUES
        }
        return {
            "status": "online" if gpu_workers else "offline",
            "workers_seen": len(worker_names),
            "gpu_workers": gpu_workers,
            "queue_depths": depths,
            "queue_depth_total": sum(depths.values()),
            "error": None,
        }
    except Exception:
        # Do not surface broker addresses, credentials, or transport exception text.
        return {
            "status": "unknown",
            "workers_seen": 0,
            "gpu_workers": [],
            "queue_depths": {},
            "queue_depth_total": None,
            "error": "worker_status_unavailable",
        }
    finally:
        redis_client.close()


def parse_dcgm_metrics(lines: Iterable[str]) -> list[dict[str, object]]:
    """Convert the DCGM Prometheus samples used by the dashboard into GPU rows."""
    devices: dict[str, dict[str, object]] = {}
    for line in lines:
        match = _SAMPLE.match(line.strip())
        if match is None or match.group("name") not in _METRIC_NAMES:
            continue
        labels = dict(_LABEL.findall(match.group("labels")))
        device = labels.get("gpu") or labels.get("UUID") or labels.get("device")
        if device is None:
            continue
        row = devices.setdefault(
            device,
            {
                "device": device,
                "name": labels.get("modelName") or labels.get("name") or "NVIDIA GPU",
            },
        )
        try:
            row[_METRIC_NAMES[match.group("name")]] = float(match.group("value"))
        except (KeyError, ValueError):
            continue
    return [devices[key] for key in sorted(devices)]


def _hardware_snapshot() -> dict[str, object]:
    url = get_settings().gpu_metrics_url
    if not url:
        return {"status": "unconfigured", "devices": []}
    try:
        with urlopen(url, timeout=1.5) as response:  # noqa: S310 - operator-configured private endpoint
            devices = parse_dcgm_metrics(response.read(2_000_000).decode("utf-8").splitlines())
        return {"status": "online" if devices else "no_gpu_samples", "devices": devices}
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError):
        return {"status": "unavailable", "devices": []}


def gpu_health_snapshot() -> dict[str, object]:
    return {"workers": _gpu_worker_snapshot(), "hardware": _hardware_snapshot()}
