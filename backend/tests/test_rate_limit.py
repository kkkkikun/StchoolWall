import pytest
from redis.asyncio import Redis

from app.utils.rate_limit import check_rate_limit


class TestRateLimit:
    """Redis 限流器"""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self, test_redis: Redis):
        key = "test:rl:allow"
        await test_redis.delete(key)
        for _ in range(5):
            await check_rate_limit(key, max_requests=5, window_seconds=60)

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, test_redis: Redis):
        key = "test:rl:block"
        await test_redis.delete(key)
        for _ in range(3):
            await check_rate_limit(key, max_requests=3, window_seconds=60)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await check_rate_limit(key, max_requests=3, window_seconds=60)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, test_redis: Redis):
        key1 = "test:rl:ind1"
        key2 = "test:rl:ind2"
        await test_redis.delete(key1)
        await test_redis.delete(key2)

        for _ in range(3):
            await check_rate_limit(key1, max_requests=3, window_seconds=60)
        await check_rate_limit(key2, max_requests=3, window_seconds=60)

    @pytest.mark.asyncio
    async def test_counter_increments(self, test_redis: Redis):
        key = "test:rl:count"
        await test_redis.delete(key)
        await check_rate_limit(key, max_requests=10, window_seconds=60)
        count = await test_redis.get(key)
        assert int(count) == 1

        await check_rate_limit(key, max_requests=10, window_seconds=60)
        count = await test_redis.get(key)
        assert int(count) == 2
