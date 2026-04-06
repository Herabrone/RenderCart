from api.usage import UsageTracker, normalize_usage_endpoint


class FakeRedis:
    def __init__(self):
        self.store = {}

    def zadd(self, key, mapping):
        bucket = self.store.setdefault(key, {})
        bucket.update(mapping)

    def zremrangebyscore(self, key, minimum, maximum):
        bucket = self.store.get(key, {})
        for member, score in list(bucket.items()):
            if minimum <= score <= maximum:
                del bucket[member]

    def zcount(self, key, minimum, _maximum):
        bucket = self.store.get(key, {})
        return sum(1 for score in bucket.values() if score >= minimum)

    def scan_iter(self, match):
        prefix = match.replace("*", "")
        for key in self.store:
            if key.startswith(prefix):
                yield key

    def zrangebyscore(self, key, minimum, _maximum, withscores=False):
        bucket = self.store.get(key, {})
        items = [(member, score) for member, score in bucket.items() if score >= minimum]
        return items if withscores else [member for member, _ in items]


def test_normalize_usage_endpoint_handles_dynamic_paths():
    assert normalize_usage_endpoint("/batch/abc/download") == "/batch/{batch_id}/download"
    assert normalize_usage_endpoint("/job/job_123") == "/job/{job_id}"


def test_usage_tracker_collects_endpoint_stats(monkeypatch):
    tracker = UsageTracker()
    tracker.redis = FakeRedis()

    monkeypatch.setattr("api.usage.time.time", lambda: 1_000)
    tracker.track_request("business_1", "/generate", success=True)
    tracker.track_request("business_1", "/generate", success=False)

    stats = tracker.get_usage_stats("business_1", days=7)

    assert stats["total_requests"] == 2
    assert stats["successful_requests"] == 1
    assert stats["failed_requests"] == 1
    assert stats["endpoints"]["/generate"] == 2
