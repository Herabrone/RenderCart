import time
import uuid
from datetime import datetime, timedelta

import redis
from config import settings


def normalize_usage_endpoint(path: str) -> str:
    if path.startswith("/api/"):
        path = path[4:]
    if path.startswith("/job/"):
        return "/job/{job_id}"
    if path.startswith("/jobs/"):
        return "/jobs/{job_id}"
    if path.startswith("/batch/") and path.endswith("/retry-failed"):
        return "/batch/{batch_id}/retry-failed"
    if path.startswith("/batch/") and path.endswith("/download"):
        return "/batch/{batch_id}/download"
    if path.startswith("/batch/"):
        return "/batch/{batch_id}"
    if path.startswith("/assets/"):
        return "/assets/{asset_id}"
    if path.startswith("/rate_limit/"):
        return "/rate_limit/{business_id}"
    return path


class UsageTracker:
    """Track API usage by business ID."""

    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True,
        )

    @staticmethod
    def _event_member(timestamp_ms: int) -> str:
        return f"{timestamp_ms}:{uuid.uuid4().hex}"

    def _prune_old(self, key: str, cutoff_ms: int) -> None:
        self.redis.zremrangebyscore(key, 0, cutoff_ms)

    def track_request(self, business_id: str, endpoint: str, success: bool = True) -> None:
        timestamp_ms = int(time.time() * 1000)
        cutoff_ms = timestamp_ms - (30 * 24 * 60 * 60 * 1000)

        request_key = f"usage:{business_id}:requests"
        endpoint_key = f"usage:{business_id}:endpoints:{endpoint}"
        outcome_key = f"usage:{business_id}:{'success' if success else 'failure'}"

        member = self._event_member(timestamp_ms)
        for key in (request_key, endpoint_key, outcome_key):
            self.redis.zadd(key, {member: timestamp_ms})
            self._prune_old(key, cutoff_ms)

    def _count_recent(self, key: str, cutoff_ms: int) -> int:
        return int(self.redis.zcount(key, cutoff_ms, "+inf"))

    def get_usage_stats(self, business_id: str, days: int = 7) -> dict:
        cutoff_ms = int(time.time() * 1000) - (days * 24 * 60 * 60 * 1000)
        safe_cutoff_ms = max(cutoff_ms, 0)
        request_key = f"usage:{business_id}:requests"
        success_key = f"usage:{business_id}:success"
        failure_key = f"usage:{business_id}:failure"

        total_requests = self._count_recent(request_key, safe_cutoff_ms)
        successful_requests = self._count_recent(success_key, safe_cutoff_ms)
        failed_requests = self._count_recent(failure_key, safe_cutoff_ms)

        endpoint_stats = {}
        endpoint_pattern = f"usage:{business_id}:endpoints:*"
        for key in self.redis.scan_iter(match=endpoint_pattern):
            endpoint = key.split(":endpoints:", 1)[1]
            endpoint_stats[endpoint] = self._count_recent(key, safe_cutoff_ms)

        return {
            "business_id": business_id,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": (successful_requests / total_requests * 100) if total_requests else 0,
            "endpoints": dict(sorted(endpoint_stats.items())),
            "time_period": {
                "days": days,
                "start": datetime.fromtimestamp(safe_cutoff_ms / 1000).isoformat(),
                "end": datetime.fromtimestamp(int(time.time())).isoformat(),
            },
        }

    def get_daily_stats(self, business_id: str, days: int = 7) -> list:
        cutoff_ms = int(time.time() * 1000) - (days * 24 * 60 * 60 * 1000)
        requests_key = f"usage:{business_id}:requests"
        recent_members = self.redis.zrangebyscore(requests_key, cutoff_ms, "+inf", withscores=True)

        daily_counts = {}
        for _, score in recent_members:
            day = datetime.fromtimestamp(score / 1000).strftime("%Y-%m-%d")
            daily_counts[day] = daily_counts.get(day, 0) + 1

        result = []
        for index in range(days):
            day = (datetime.now() - timedelta(days=index)).strftime("%Y-%m-%d")
            result.append({"date": day, "requests": daily_counts.get(day, 0)})
        return result

    def get_top_businesses(self, limit: int = 10) -> list:
        return []
