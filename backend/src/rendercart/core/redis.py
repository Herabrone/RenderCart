from typing import cast

from redis import Redis

from rendercart.core.config import get_settings

redis_client = Redis.from_url(get_settings().redis_url, decode_responses=True)


_INCREMENT_WITH_TTL = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


def increment_window(key: str, ttl_seconds: int) -> int:
    result = redis_client.eval(_INCREMENT_WITH_TTL, 1, key, str(ttl_seconds))
    return int(cast(str | int, result))
