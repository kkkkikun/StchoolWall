"""应用在 /metrics 暴露的指标面。

/metrics 用 prometheus_client 的 generate_latest() 渲染默认 registry，
所以这里注册的指标名就是 Prometheus 能抓到的指标名 —— 告警规则引用的指标
必须出现在这里，否则规则永远不触发（空转）。

任务队列信号只输出聚合计数：不含 payload、证件、token 或任何用户内容。
DB/Redis 信号同样只输出计数与比率：连接池用了几条连接、占了连接预算的多少，
Redis 调用失败了几次 —— 不带连接串、键名、payload 或任何用户内容。
备份侧信号只输出计数、时长与布尔：距最近一次成功备份的秒数、最近一次备份
尝试是否成功、累计失败次数 —— 不带备份路径、对象存储密钥、连接串或备份内容。
"""
import logging
from datetime import datetime, timezone

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import func, select

from app.backup_status import read_backup_status
from app.config import settings
from app.database import async_session, engine
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

# DB/Redis 的应用侧信号：连接池用了几条连接、占了连接预算的多少（比率），
# 以及 Redis 调用失败了几次（计数）。锁等待、主机容量一类信号需要
# postgres_exporter / node_exporter，不在这里冒充已覆盖。
DB_POOL_USED = Gauge("schoolwall_db_pool_used_connections",
                      "Database connections currently in use by this process")
DB_POOL_OVERFLOW = Gauge("schoolwall_db_pool_overflow_connections",
                          "Database connections in use beyond DB_POOL_SIZE")
DB_POOL_MAX = Gauge("schoolwall_db_pool_max_connections",
                     "Database connection budget of this process (DB_POOL_SIZE plus DB_MAX_OVERFLOW)")
DB_POOL_USAGE_RATIO = Gauge("schoolwall_db_pool_usage_ratio",
                            "Used share of the database connection budget (0 to 1)")
REDIS_FAILURES = Counter("schoolwall_redis_failures_total",
                          "Redis calls that failed in this process")

# 备份侧信号：最近一次成功备份距今的秒数（时长）、最近一次备份尝试是否成功
# （布尔）、累计失败的备份次数（计数）与「状态是否读到了」（布尔）。采集只输出
# 计数、时长与布尔，不带备份路径、对象存储密钥、连接串或备份内容。
BACKUP_LAST_SUCCESS_AGE = Gauge("schoolwall_backup_last_success_age_seconds",
                                "Seconds since the last successful backup; -1 when unknown")
BACKUP_LAST_ATTEMPT_SUCCEEDED = Gauge("schoolwall_backup_last_attempt_succeeded",
                                       "1 when the most recent recorded backup attempt succeeded")
BACKUP_FAILURES = Counter("schoolwall_backup_failures_total",
                           "Failed backup attempts observed by this process")
BACKUP_STATUS_COLLECTION_OK = Gauge("schoolwall_backup_status_collection_ok",
                                     "1 when the backup status file was read and parsed")

# 累计失败数的基线：状态文件里的失败数是累计值，应用重启后第一次读到它时
# 只记基线（那是之前就发生过的失败，不是「增长」）。
_backup_failure_baseline: int | None = None

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


def record_redis_failure() -> None:
    """记一次 Redis 调用失败。

    只加一个计数：失败次数本身不含键名、payload 或任何用户内容。
    """
    REDIS_FAILURES.inc()


def _pool_count(pool, name: str, default: int = 0) -> int:
    """读连接池的一个计数；读不到就按默认值记，不让 /metrics 因探测失败而 500。"""
    reader = getattr(pool, name, None)
    if reader is None:
        return default
    try:
        return int(reader())
    except Exception as exc:
        logger.warning("db pool metric %s unavailable error=%s", name, type(exc).__name__)
        return default


def db_pool_usage(pool=None) -> tuple[int, int, int, float]:
    """本进程的数据库连接池用量：(已用连接数, 溢出连接数, 连接预算, 使用率)。

    已用连接数取连接池当前借出的连接数（已含超出 DB_POOL_SIZE 的那几条）；
    连接预算 = DB_POOL_SIZE + DB_MAX_OVERFLOW，与 docs/production/runbook.md
    「数据库连接总预算」的口径一致。使用率是比率，用来对照 runbook
    「首发告警目标」表 DB/Redis 行的 pool使用>80%。这些数字只来自进程内的
    连接池状态，不查库、也不带任何连接串或用户内容。

    pool 参数只为用例可测：默认取应用自己的连接池。
    """
    pool = engine.pool if pool is None else pool
    used = _pool_count(pool, "checkedout")
    # SQLAlchemy 的 overflow() 在没有溢出时是负数（最低到 -pool_size），
    # 负数表示「还没用满」，一律按 0 记。
    overflow = max(0, _pool_count(pool, "overflow"))
    budget = _pool_count(pool, "size", settings.DB_POOL_SIZE) + settings.DB_MAX_OVERFLOW
    return used, overflow, budget, (used / budget if budget > 0 else 0.0)


def refresh_db_pool_metrics() -> None:
    """刷新数据库连接池指标。

    连接池状态是进程内的，不需要查库：数据库不可用时这些数字依然有意义
    （连接打满往往正是数据库变慢的先兆），采集本身不会失败。
    """
    used, overflow, budget, ratio = db_pool_usage()
    DB_POOL_USED.set(used)
    DB_POOL_OVERFLOW.set(overflow)
    DB_POOL_MAX.set(budget)
    DB_POOL_USAGE_RATIO.set(ratio)


def refresh_backup_metrics() -> None:
    """刷新备份侧指标；状态文件读不到只把 collection_ok 置 0，不抛异常。"""
    status = read_backup_status(settings.BACKUP_STATUS_FILE)
    BACKUP_STATUS_COLLECTION_OK.set(1 if status.readable else 0)
    BACKUP_LAST_SUCCESS_AGE.set(status.last_success_age_seconds)
    BACKUP_LAST_ATTEMPT_SUCCEEDED.set(1 if status.last_attempt_succeeded else 0)
    _observe_backup_failures(status.failures)


def _observe_backup_failures(failures: int) -> None:
    """累计失败数只在观察到增长时递增。

    状态文件里的失败数是累计值：应用重启后第一次读到它时只记基线 —— 那是
    之前就发生过的失败，不是「增长」；之后每次读到更大的值才递增计数。
    「最近一次备份是否成功」另外单独暴露，停机期间发生的失败不会因此丢失。
    """
    global _backup_failure_baseline
    if _backup_failure_baseline is None:
        _backup_failure_baseline = failures
        return
    if failures > _backup_failure_baseline:
        BACKUP_FAILURES.inc(failures - _backup_failure_baseline)
    _backup_failure_baseline = failures
