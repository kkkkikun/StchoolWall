"""备份侧信号在 /metrics 上的回归测试。

`docs/production/runbook.md` 的「首发告警目标」表把备份行列为首发告警目标
（最新备份>26小时、失败增长），对应的告警规则引用的是应用 /metrics 暴露的
备份新鲜度与备份失败信号。这里固定五件事：

1. /metrics 真的暴露备份信号，且数值与状态文件一致；
2. 状态文件读不到（没配路径、文件不存在、内容坏了）时 /metrics 仍可抓取，
   并把「状态未知」如实暴露出来（否则规则会永远空转）；
3. 采集只输出计数、时长与布尔：备份路径、密钥与备份内容一律不进指标；
4. 失败计数只在失败数增长时递增（累计值不是「增长」）；
5. 最近一次备份是否成功单独暴露：停机期间发生的失败不会因此丢失。
"""
import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

import app.metrics as metrics_module
from app.config import settings
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


def _write_status(path, *, ok: bool, failures: int, success_at: datetime | None) -> None:
    path.write_text(json.dumps({
        "version": 1,
        "attempts": failures + 1,
        "failures": failures,
        "last_attempt_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_attempt_ok": ok,
        "last_success_at": success_at.strftime("%Y-%m-%dT%H:%M:%SZ") if success_at else None,
    }), encoding="utf-8")


async def test_metrics_expose_the_backup_signals(client: AsyncClient, monkeypatch, tmp_path):
    """备份新鲜度、是否成功与状态可读性必须出现在 /metrics 上。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    status_file = tmp_path / "backup_status.json"
    _write_status(status_file, ok=True, failures=0,
                  success_at=datetime.now(timezone.utc) - timedelta(hours=2))
    monkeypatch.setattr(settings, "BACKUP_STATUS_FILE", str(status_file))

    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert _metric_value(text, "schoolwall_backup_status_collection_ok") == 1.0
    assert _metric_value(text, "schoolwall_backup_last_attempt_succeeded") == 1.0
    age = _metric_value(text, "schoolwall_backup_last_success_age_seconds")
    assert 7100 < age < 7300  # 两小时前的那次成功备份


async def test_a_failed_backup_is_reported_as_not_succeeded(client: AsyncClient, monkeypatch, tmp_path):
    """最近一次备份失败时，布尔信号必须是 0。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    status_file = tmp_path / "backup_status.json"
    _write_status(status_file, ok=False, failures=1,
                  success_at=datetime.now(timezone.utc) - timedelta(hours=30))
    monkeypatch.setattr(settings, "BACKUP_STATUS_FILE", str(status_file))

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert _metric_value(response.text, "schoolwall_backup_last_attempt_succeeded") == 0.0
    assert _metric_value(response.text, "schoolwall_backup_status_collection_ok") == 1.0


async def test_an_unreadable_status_keeps_metrics_scrapeable(client: AsyncClient, monkeypatch, tmp_path):
    """状态文件读不到时 /metrics 仍要返回，并把「状态未知」如实暴露。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    monkeypatch.setattr(settings, "BACKUP_STATUS_FILE", str(tmp_path / "missing.json"))

    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert _metric_value(text, "schoolwall_backup_status_collection_ok") == 0.0
    # 未知按 -1 记：不能被「>26 小时」的阈值误判成过期。
    assert _metric_value(text, "schoolwall_backup_last_success_age_seconds") == -1.0


async def test_a_broken_status_file_is_treated_as_unknown(client: AsyncClient, monkeypatch, tmp_path):
    """状态文件内容坏了同样按未知记，/metrics 不许因此 500。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    status_file = tmp_path / "backup_status.json"
    status_file.write_text("not json at all", encoding="utf-8")
    monkeypatch.setattr(settings, "BACKUP_STATUS_FILE", str(status_file))

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert _metric_value(response.text, "schoolwall_backup_status_collection_ok") == 0.0


async def test_backup_metrics_carry_no_paths_keys_or_backup_content(
    client: AsyncClient, monkeypatch, tmp_path
):
    """采集只输出计数、时长与布尔：备份路径、密钥与备份内容一律不进指标。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    status_file = tmp_path / "backup_status.json"
    status_file.write_text(json.dumps({
        "version": 1,
        "attempts": 2,
        "failures": 1,
        "last_attempt_at": "2026-11-04T05:10:58Z",
        "last_attempt_ok": False,
        "last_success_at": "2026-11-03T05:10:58Z",
        "secret_marker": "COS_SECRET_KEY_do_not_expose",
    }), encoding="utf-8")
    monkeypatch.setattr(settings, "BACKUP_STATUS_FILE", str(status_file))

    response = await client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    assert str(status_file) not in text
    assert str(tmp_path) not in text
    assert "COS_SECRET_KEY_do_not_expose" not in text


async def test_the_failure_counter_only_grows_when_the_failure_count_grows(
    client: AsyncClient, monkeypatch, tmp_path
):
    """状态文件里的失败数是累计值：只在观察到增长时才算「失败增长」。"""
    monkeypatch.setattr(metrics_module, "async_session", TestSession)
    status_file = tmp_path / "backup_status.json"
    _write_status(status_file, ok=False, failures=0,
                  success_at=datetime.now(timezone.utc) - timedelta(hours=1))
    monkeypatch.setattr(settings, "BACKUP_STATUS_FILE", str(status_file))
    before = metrics_module.BACKUP_FAILURES._value.get()

    await client.get("/metrics")  # 第一次只记基线
    assert metrics_module.BACKUP_FAILURES._value.get() == before

    _write_status(status_file, ok=False, failures=1,
                  success_at=datetime.now(timezone.utc) - timedelta(hours=1))
    response = await client.get("/metrics")

    assert metrics_module.BACKUP_FAILURES._value.get() == before + 1
    assert _counter_value(response.text, "schoolwall_backup_failures_total") >= 1
