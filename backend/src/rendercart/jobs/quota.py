from redis import Redis

from rendercart.core.config import get_settings

redis_client = Redis.from_url(get_settings().redis_url, decode_responses=True)
_RESERVE = """
local count = tonumber(redis.call('GET', KEYS[1]) or '0')
local maximum = tonumber(ARGV[1])
if count >= maximum then return 0 end
count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
return count
"""
_RESERVE_AMOUNT = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local amount = tonumber(ARGV[1])
local maximum = tonumber(ARGV[2])
if current + amount > maximum then return 0 end
current = redis.call('INCRBY', KEYS[1], amount)
if current == amount then redis.call('EXPIRE', KEYS[1], ARGV[3]) end
return current
"""


def reserve_counter(key: str, maximum: int, ttl_seconds: int) -> bool:
    return bool(redis_client.eval(_RESERVE, 1, key, str(maximum), str(ttl_seconds)))


def release_key(key: str) -> None:
    redis_client.decr(key)


def reserve_amount(key: str, amount: int, maximum: int, ttl_seconds: int) -> bool:
    if amount <= 0 or maximum <= 0:
        return False
    return bool(
        redis_client.eval(_RESERVE_AMOUNT, 1, key, str(amount), str(maximum), str(ttl_seconds))
    )


def release_amount(key: str, amount: int) -> None:
    if amount > 0:
        redis_client.eval(
            "local current = tonumber(redis.call('GET', KEYS[1]) or '0'); "
            "if current <= tonumber(ARGV[1]) then redis.call('DEL', KEYS[1]); "
            "else redis.call('DECRBY', KEYS[1], ARGV[1]); end; return 1",
            1,
            key,
            str(amount),
        )
