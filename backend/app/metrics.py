"""应用在 /metrics 暴露的指标面。

/metrics 用 prometheus_client 的 generate_latest() 渲染默认 registry，
所以这里注册的指标名就是 Prometheus 能抓到的指标名 —— 告警规则引用的指标
必须出现在这里，否则规则永远不触发（空转）。

任务队列信号只输出聚合计数：不含 payload、证件、token 或任何用户内容。
"""
import logging
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select

from app.database import async_session
from app.models.job import Job

logger = logging.getLogger("schoolwall.metrics")

HTTP_REQUESTS = Counter("schoolwall_http_requests_total", "API requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram("schoolwall_http_duration_seconds", "API latency", ["method", "route"],
                          buckets=(.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))

JOBS_PENDING = Gauge("schoolwall_jobs_pending", "Jobs waiting for the worker to pick them up")
JOBS_OLDEST_PENDING_AGE = Gauge(
    "schoolwall_jobs_oldest_pending_age_seconds",
    "Waiting seconds of the oldest pending job, measured from its enqueue time")
JOBS_DEAD = Gauge("schoolwall_jobs_dead", "Jobs in the dead letter state")
JOBS_RUNNING_LEASE_EXPIRED = Gauge("schoolwall_jobs_running_lease_expired",
                                    "Running jobs whose lease has expired")
JOBS_METRICS_COLLECTION_OK = Gauge("schoolwall_jobs_metrics_collection_ok",
                                    "1 when the last job metric collection succeeded, 0 otherwise")

# 一条聚合查询取全部任务队列信号；租约是否过期按数据库时钟判断。
_JOB_STATS = select(
    func.count(Job.id).filter(Job.status == "pending"),
    func.min(Job.created_at).filter(Job.status == "pending"),
    func.count(Job.id).filter(Job.status == "dead"),
    func.count(Job.id).filter(Job.status == "running", Job.lease_until < func.now()),
)


def _oldest_pending_age_seconds(oldest_pending_at) -> float:
    """最老待处理任务的等待秒数。

    按入队时间（created_at）算：任务从入队起就在等待，退避重排只推迟下一次
    可执行时间、并不会让它不再积压。口径与 docs/production/capacity.md 里
    「待审任务最旧年龄」一致。
    """
    if oldest_pending_at is None:
        return 0.0
    if oldest_pending_at.tzinfo is None:
        oldest_pending_at = oldest_pending_at.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - oldest_pending_at).total_seconds())


async def refresh_job_metrics() -> None:
    """刷新任务队列指标；采集失败只把 collection_ok 置 0，不抛异常。

    /metrics 是 Prometheus 的抓取入口：数据库不可用时它必须仍能返回 RED 指标，
    否则一次数据库故障会把错误率与时延信号一起抹掉。
    """
    try:
        async with async_session() as db:
            pending, oldest_pending_at, dead, lease_expired = (await db.execute(_JOB_STATS)).one()
    except Exception as exc:
        JOBS_METRICS_COLLECTION_OK.set(0)
        logger.warning("job metrics collection failed error=%s", type(exc).__name__)
        return
    JOBS_PENDING.set(pending)
    JOBS_DEAD.set(dead)
    JOBS_RUNNING_LEASE_EXPIRED.set(lease_expired)
    JOBS_OLDEST_PENDING_AGE.set(_oldest_pending_age_seconds(oldest_pending_at))
    JOBS_METRICS_COLLECTION_OK.set(1)
