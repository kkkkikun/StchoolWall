"""DB/Redis 应用侧信号在 /metrics 上的回归测试。

`docs/production/runbook.md` 的「首发告警目标」表把 DB/Redis 行列为首发告警目标
（pool 使用>80% 持续 10 分钟、Redis 失败>0），对应的告警规则引用的是应用
/metrics 暴露的连接池与 Redis 失败信号。这里固定四件事：

1. /metrics 真的暴露连接池用量与 Redis 失败计数，且数值与连接池实际状态一致；
2. Redis 调用失败会计数，且异常照旧向上抛（错误码语义不变）；
3. 采集只输出计数与比率：连接串、口令、键名与用户内容一律不进指标；
4. 数据库不可用时连接池信号依然在（连接池状态是进程内的，不查库）。
"""
import pytest
from httpx import AsyncClient

import app.metrics as metrics_module
from app.config import settings
from app.metrics import db_pool_usage
from app.utils.redis import InstrumentedRedis
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio


def _metric_value(text: str, name: str) -> float:
    for line in text.splitlines():
        if line.startswith(f"{name} ") or line.startswith(f"{name}{{"):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"metric is not exposed: {name}")


def _counter_value(text: str, name: str) -> float:
    """计数器的当前值（没有样本时按 0 计）。"""
    for line in text.splitlines():
        if line.startswith(f"{name} "):
            return float(line.rsplit(" ", 1)[1])
    return 0.0


class _FailingRedis:
    """总是失败的 Redis 客户端替身。"""

    async def get(self, *args, **kwargs):
        raise ConnectionError("redis is unreachable")


async def test_metrics_expose_the_db_pool_signals(client: AsyncClient, monkeypatch):
    """连接池用量、预算与使用率必须与实际连接池状态一致。"""
    # 用测试会话采集队列信号：应用自己的引擎连接会跨事件循环复用，测试里不碰。
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    budget = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    used = _metric_value(text, "schoolwall_db_pool_used_connections")
    assert _metric_value(text, "schoolwall_db_pool_max_connections") == budget
    assert used >= 0
    overflow = _metric_value(text, "schoolwall_db_pool_overflow_connections")
    assert overflow >= 0
    assert overflow <= settings.DB_MAX_OVERFLOW
    ratio = _metric_value(text, "schoolwall_db_pool_usage_ratio")
    assert ratio == pytest.approx(used / budget)
    assert 0.0 <= ratio <= 1.0


async def test_db_pool_usage_counts_a_checked_out_connection():
    """连接被借出时，使用率必须跟着涨（否则 80% 阈值永远不会触发）。"""

    class _BusyPool:
        def checkedout(self):
            return 12

        def overflow(self):
            return 2

        def size(self):
            return 10

    used, overflow, budget, ratio = db_pool_usage(_BusyPool())
    assert used == 12
    assert overflow == 2
    assert budget == settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    assert ratio == pytest.approx(12 / budget)


async def test_db_pool_usage_treats_a_negative_overflow_as_zero():
    """SQLAlchemy 的 overflow() 在没溢出时是负数，不能当成负的溢出连接。"""

    class _IdlePool:
        def checkedout(self):
            return 3

        def overflow(self):
            return -10

        def size(self):
            return 10

    used, overflow, budget, ratio = db_pool_usage(_IdlePool())
    assert used == 3
    assert overflow == 0
    assert ratio == pytest.approx(3 / budget)


async def test_db_pool_usage_survives_a_pool_that_cannot_be_probed():
    """连接池读不到数字时按默认值记，/metrics 不因探测失败而 500。"""

    class _BrokenPool:
        def checkedout(self):
            raise NotImplementedError("pool does not support checkedout")

        def overflow(self):
            raise NotImplementedError("pool does not support overflow")

        def size(self):
            raise NotImplementedError("pool does not support size")

    used, overflow, budget, ratio = db_pool_usage(_BrokenPool())
    assert used == 0
    assert overflow == 0
    assert budget == settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    assert ratio == 0.0


async def test_metrics_expose_the_redis_failure_counter(client: AsyncClient, monkeypatch):
    """/metrics 必须暴露 Redis 失败计数。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    response = await client.get("/metrics")

    assert response.status_code == 200
    assert "schoolwall_redis_failures_total" in response.text


async def test_a_failing_redis_call_is_counted_and_still_raises():
    """失败的 Redis 调用要计数，异常照旧向上抛（错误码语义不变）。"""
    before = metrics_module.REDIS_FAILURES._value.get()

    with pytest.raises(ConnectionError):
        await InstrumentedRedis(_FailingRedis()).get("some-key")

    assert metrics_module.REDIS_FAILURES._value.get() == before + 1


async def test_a_failing_redis_call_through_the_application_client_is_counted(client: AsyncClient, monkeypatch):
    """应用自己的 Redis 客户端失败时，计数也会涨。"""
    import app.utils.redis as redis_module

    raw = redis_module.redis_client._client

    async def _boom(*args, **kwargs):
        raise ConnectionError("redis is unreachable")

    monkeypatch.setattr(raw, "get", _boom)
    before = metrics_module.REDIS_FAILURES._value.get()

    with pytest.raises(ConnectionError):
        await redis_module.redis_client.get("some-key")

    assert metrics_module.REDIS_FAILURES._value.get() == before + 1
    response = await client.get("/metrics")
    assert _counter_value(response.text, "schoolwall_redis_failures_total") >= 1


async def test_metrics_carry_no_credentials_or_user_content(client: AsyncClient, monkeypatch):
    """采集只输出计数与比率：连接串、口令与用户内容一律不进指标。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert settings.REDIS_URL not in text
    assert settings.DATABASE_URL not in text
    password = settings.REDIS_URL.split("@")[0].split("://")[-1]
    if password:
        assert password not in text
