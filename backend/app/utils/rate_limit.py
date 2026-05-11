from fastapi import HTTPException, status

from app.utils.redis import redis_client


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, window_seconds)
    if current > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试",
        )
