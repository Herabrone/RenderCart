import redis
from config import settings
from fastapi import HTTPException, status

rate_limit_redis = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    decode_responses=True,
)


def get_rate_limit_status(business_id: str) -> dict:
    key = f"rate_limit:{business_id}"
    current = rate_limit_redis.get(key)
    return {
        "business_id": business_id,
        "current_requests": int(current) if current else 0,
        "limit": settings.rate_limit_per_minute,
        "reset_time": "1 minute",
    }


async def check_rate_limit(business_id: str) -> None:
    key = f"rate_limit:{business_id}"
    current = rate_limit_redis.incr(key)
    if current == 1:
        rate_limit_redis.expire(key, 60)

    if current > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Rate limit exceeded. Maximum "
                f"{settings.rate_limit_per_minute} requests per minute."
            ),
        )
