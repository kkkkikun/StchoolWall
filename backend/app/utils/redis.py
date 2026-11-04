import functools
import inspect

import redis.asyncio as redis

from app.config import settings


def _count_failure() -> None:
    """记一次 Redis 调用失败（延迟导入，指标依赖缺失时不阻断业务）。"""
    try:
        from app.metrics import record_redis_failure
    except ImportError:  # pragma: no cover - 指标面不可用时业务行为不变
        return
    record_redis_failure()


class InstrumentedRedis:
    """Redis 客户端代理：调用失败时计一次数，其余行为原样透传。

    runbook 的「首发告警目标」表把 Redis 失败>0 列为首发告警目标，值班人需要
    一个可抓取的应用侧失败计数。计数只记次数：不含键名、payload、连接串或
    任何用户内容，异常本身照旧向上抛（错误码语义不变）。

    redis-py 5.x 的异步客户端里，命令方法本身是普通函数、返回协程，所以这里
    既包同步抛出的异常，也包协程 await 时的异常，两种失败都算一次失败。
    """

    def __init__(self, client):
        self._client = client

    def __getattr__(self, name):
        attribute = getattr(self._client, name)
        if not callable(attribute):
            return attribute

        @functools.wraps(attribute)
        def _counting(*args, **kwargs):
            try:
                result = attribute(*args, **kwargs)
            except Exception:
                _count_failure()
                raise
            if not inspect.isawaitable(result):
                return result
            return self._count_awaitable(result)

        return _counting

    @staticmethod
    async def _count_awaitable(awaitable):
        try:
            return await awaitable
        except Exception:
            _count_failure()
            raise


redis_client = InstrumentedRedis(
    redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
                   max_connections=50))
