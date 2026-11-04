"""任务队列信号在 /metrics 上的回归测试。

`docs/production/runbook.md` 的「首发告警目标」表把 jobs 列为首发告警目标
（最老 pending>10 分钟、dead>0、running 租约过期），对应的告警规则引用的是
应用 /metrics 暴露的四个指标。这里固定三件事：

1. /metrics 真的暴露这四个任务队列信号，且数值与库里的任务状态一致；
2. 采集只输出聚合，绝不把任务内容（payload）带进指标；
3. 数据库不可用时 /metrics 仍然返回 200 并保留 RED 指标 —— 采集失败只把
   collection_ok 置 0，不能连错误率与时延信号一起抹掉。
"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

import app.metrics as metrics_module
from app.models.job import Job
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio

OLD_PENDING_AGE_SECONDS = 900


def _metric_value(text: str, name: str) -> float:
    for line in text.splitlines():
        if line.startswith(f"{name} ") or line.startswith(f"{name}{{"):
            return float(line.rsplit(" ", 1)[1])
    raise AssertionError(f"metric is not exposed: {name}")


async def _insert_job(**values) -> Job:
    async with TestSession() as db:
        job = Job(**values)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job


async def test_metrics_expose_the_job_queue_signals(client: AsyncClient, monkeypatch):
    """四个任务队列信号必须与库里的任务状态一致。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    now = datetime.now(timezone.utc)
    await _insert_job(kind="moderate_post", dedupe_key="metrics-old-pending",
                      payload={"note": "synthetic-payload-must-not-leak"}, status="pending",
                      attempts=0, max_attempts=5, created_at=now - timedelta(seconds=OLD_PENDING_AGE_SECONDS),
                      updated_at=now - timedelta(seconds=OLD_PENDING_AGE_SECONDS), available_at=now)
    await _insert_job(kind="moderate_post", dedupe_key="metrics-fresh-pending",
                      payload={}, status="pending", attempts=0, max_attempts=5,
                      created_at=now, updated_at=now, available_at=now)
    await _insert_job(kind="moderate_post", dedupe_key="metrics-dead",
                      payload={}, status="dead", attempts=5, max_attempts=5,
                      created_at=now, updated_at=now, available_at=now)
    await _insert_job(kind="moderate_post", dedupe_key="metrics-running-expired",
                      payload={}, status="running", attempts=1, max_attempts=5,
                      created_at=now, updated_at=now, available_at=now,
                      lease_until=now - timedelta(seconds=30))
    await _insert_job(kind="moderate_post", dedupe_key="metrics-running-valid",
                      payload={}, status="running", attempts=1, max_attempts=5,
                      created_at=now, updated_at=now, available_at=now,
                      lease_until=now + timedelta(seconds=120))

    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert _metric_value(text, "schoolwall_jobs_pending") == 2
    assert _metric_value(text, "schoolwall_jobs_dead") == 1
    assert _metric_value(text, "schoolwall_jobs_running_lease_expired") == 1
    age = _metric_value(text, "schoolwall_jobs_oldest_pending_age_seconds")
    assert OLD_PENDING_AGE_SECONDS <= age <= OLD_PENDING_AGE_SECONDS + 60
    assert _metric_value(text, "schoolwall_jobs_metrics_collection_ok") == 1
    # 只输出聚合：任务内容绝不能出现在指标里。
    assert "synthetic-payload-must-not-leak" not in text


async def test_metrics_survive_a_database_failure(client: AsyncClient, monkeypatch):
    """数据库不可用时 /metrics 仍返回 200，并保留 RED 指标。"""
    class _BoomSessionFactory:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise ConnectionRefusedError(111, "Connection refused")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(metrics_module, "async_session", _BoomSessionFactory)
    # 先打一次普通请求，让 RED 指标有样本，再验证数据库故障不会把它们抹掉。
    await client.get("/health/live")

    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert _metric_value(text, "schoolwall_jobs_metrics_collection_ok") == 0
    assert "schoolwall_http_requests_total" in text
    assert "schoolwall_http_duration_seconds_bucket" in text
