"""告警规则的可抓取性守卫回归。

`docs/production/runbook.md` 的「首发告警目标」表把 jobs、DB/Redis、备份与
容量/证书列为首发告警目标，但规则文件里如果引用了没人暴露的指标，规则就永远
不触发（空转）：值班人以为「已配置」，实际收不到信号。本用例既跑真实守卫脚本
锁住仓库当前的 `deploy/monitoring/alerts.yml`，也用临时文件证明「引用了不可抓取
指标的规则」与「一个指标都没引用的规则」确实会被拦下，并锁住 jobs、DB/Redis、
备份与容量规则的阈值与持续时长仍然照抄 runbook 的表。

容量信号由 node_exporter 提供、DB 锁等待信号由 postgres_exporter 提供：指标名在守卫里
显式登记，exporter 还必须接进监控栈（compose 里有服务、prometheus.yml 里有抓取作业），
否则规则照样是空转。锁等待规则的阈值照抄 runbook 的 DB/Redis 行（锁等待会话>0、
死锁增长>0），连接串与口令只走只读的运行时配置、不得入库。
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_monitoring_alerts.py"
sys.path.insert(0, str(ROOT / "scripts"))

import check_monitoring_alerts as guard  # noqa: E402

JOB_METRICS = (
    "schoolwall_jobs_pending",
    "schoolwall_jobs_oldest_pending_age_seconds",
    "schoolwall_jobs_dead",
    "schoolwall_jobs_running_lease_expired",
)

# DB/Redis 的应用侧信号：连接池用量、连接预算、使用率与 Redis 失败计数。
DB_REDIS_METRICS = (
    "schoolwall_db_pool_used_connections",
    "schoolwall_db_pool_overflow_connections",
    "schoolwall_db_pool_max_connections",
    "schoolwall_db_pool_usage_ratio",
    "schoolwall_redis_failures_total",
)

# 备份侧信号：最近一次成功备份距今的秒数、最近一次尝试是否成功、累计失败次数
# 与「状态是否读到了」。
BACKUP_METRICS = (
    "schoolwall_backup_last_success_age_seconds",
    "schoolwall_backup_last_attempt_succeeded",
    "schoolwall_backup_failures_total",
    "schoolwall_backup_status_collection_ok",
)

# 主机容量信号（node_exporter）：根文件系统的可用与总容量、可用与总内存。
CAPACITY_METRICS = (
    "node_filesystem_avail_bytes",
    "node_filesystem_size_bytes",
    "node_memory_MemAvailable_bytes",
    "node_memory_MemTotal_bytes",
)

# DB 锁等待信号（postgres_exporter）：会话数（按 wait_event_type 维度）、死锁计数
# 与锁总数。
POSTGRES_METRICS = (
    "pg_stat_activity_count",
    "pg_stat_database_deadlocks",
    "pg_locks_count",
)


def runbook_row(prefix: str) -> str:
    text = (ROOT / "docs/production/runbook.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith(f"| {prefix} |"):
            return line
    raise AssertionError(f"runbook 必须保留「首发告警目标」表里的 {prefix} 行")


def runbook_jobs_row() -> str:
    return runbook_row("jobs")


def runbook_db_redis_row() -> str:
    return runbook_row("DB/Redis")


def runbook_backup_row() -> str:
    return runbook_row("备份")


def runbook_capacity_row() -> str:
    return runbook_row("容量/证书")


def runbook_lock_wait_thresholds() -> tuple[int, int]:
    """runbook 的 DB/Redis 行里收敛后的两个锁等待阈值。

    该行原本只写「锁等待上升」，没有数值；收敛后的口径是「锁等待会话>0」与
    「死锁增长>0」，两个数字都必须能从表里读出来，规则才允许照抄。
    """
    row = runbook_db_redis_row()
    waits = re.search(r"锁等待会话>(\d+)", row)
    deadlocks = re.search(r"死锁增长>(\d+)", row)
    assert waits is not None, "runbook 的 DB/Redis 行必须写明锁等待会话阈值"
    assert deadlocks is not None, "runbook 的 DB/Redis 行必须写明死锁增长阈值"
    return int(waits.group(1)), int(deadlocks.group(1))


class MonitoringAlertsGuardTests(unittest.TestCase):
    def run_guard(self, alerts: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(alerts)],
            capture_output=True, text=True,
        )

    def test_repository_rules_only_reference_scrapeable_metrics(self):
        result = self.run_guard(guard.DEFAULT_ALERTS)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("all referenced metrics are scrapeable", result.stdout)

    def test_rule_referencing_an_unexposed_metric_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            alerts = Path(directory) / "alerts.yml"
            alerts.write_text(
                "groups:\n"
                "  - name: schoolwall\n"
                "    rules:\n"
                "      - alert: SchoolWallJobsBacklog\n"
                "        expr: schoolwall_jobs_oldest_pending_age_seconds > 600\n"
                "        for: 5m\n"
                "      - alert: SchoolWallGhostMetric\n"
                "        expr: schoolwall_jobs_never_exposed > 0\n"
                "        for: 0m\n",
                encoding="utf-8",
            )
            result = self.run_guard(alerts)
        self.assertNotEqual(result.returncode, 0, "引用了没人暴露的指标必须立刻失败")
        self.assertIn("schoolwall_jobs_never_exposed", result.stdout + result.stderr)

    def test_rule_without_an_expression_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            alerts = Path(directory) / "alerts.yml"
            alerts.write_text(
                "groups:\n"
                "  - name: schoolwall\n"
                "    rules:\n"
                "      - alert: SchoolWallEmpty\n",
                encoding="utf-8",
            )
            result = self.run_guard(alerts)
        self.assertNotEqual(result.returncode, 0, "没有表达式的规则必须立刻失败")
        self.assertIn("without an expr", result.stdout + result.stderr)

    def test_rule_referencing_no_metric_at_all_is_rejected(self):
        """恒真或恒假的规则与告警目标无关，同样要拦下。"""
        with tempfile.TemporaryDirectory() as directory:
            alerts = Path(directory) / "alerts.yml"
            alerts.write_text(
                "groups:\n"
                "  - name: schoolwall\n"
                "    rules:\n"
                "      - alert: SchoolWallAlwaysTrue\n"
                "        expr: 1 > 0\n"
                "        for: 0m\n",
                encoding="utf-8",
            )
            result = self.run_guard(alerts)
        self.assertNotEqual(result.returncode, 0, "一个指标都没引用的规则必须立刻失败")
        self.assertIn("references no metric", result.stdout + result.stderr)

    def test_job_queue_metrics_are_exposed_by_the_application(self):
        exposed = guard.app_metric_names()
        for metric in JOB_METRICS:
            self.assertIn(metric, exposed, f"应用 /metrics 必须暴露 {metric}")

    def test_db_redis_metrics_are_exposed_by_the_application(self):
        """DB/Redis 的应用侧信号必须真的可抓取，否则规则就是空转。"""
        exposed = guard.app_metric_names()
        for metric in DB_REDIS_METRICS:
            self.assertIn(metric, exposed, f"应用 /metrics 必须暴露 {metric}")

    def test_metric_extraction_ignores_functions_and_keywords(self):
        expr = ('histogram_quantile(0.95, sum by (le) '
                '(rate(schoolwall_http_duration_seconds_bucket{route=~"/api/.*"}[5m]))) > 1')
        self.assertEqual(guard.metric_names_in(expr), {"schoolwall_http_duration_seconds_bucket"})
        self.assertEqual(
            guard.metric_names_in('probe_success{job="schoolwall-probes"} == 0'),
            {"probe_success"},
        )
        self.assertEqual(
            guard.metric_names_in("increase(schoolwall_redis_failures_total[5m]) > 0"),
            {"schoolwall_redis_failures_total"},
        )

    def test_job_rules_match_the_runbook_alert_targets(self):
        minutes = [int(value) for value in re.findall(r"(\d+)\s*分钟", runbook_jobs_row())]
        self.assertGreaterEqual(len(minutes), 2, "runbook 的 jobs 行必须写明积压阈值与持续时长")
        threshold_seconds, duration_minutes = minutes[0] * 60, minutes[1]
        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        self.assertIn("SchoolWallJobsBacklog", rules)
        self.assertEqual(
            rules["SchoolWallJobsBacklog"]["expr"],
            f"schoolwall_jobs_oldest_pending_age_seconds > {threshold_seconds}",
        )
        self.assertEqual(str(rules["SchoolWallJobsBacklog"]["for"]), f"{duration_minutes}m")
        self.assertIn("SchoolWallJobsDeadLetters", rules)
        self.assertEqual(rules["SchoolWallJobsDeadLetters"]["expr"], "schoolwall_jobs_dead > 0")
        self.assertIn("SchoolWallJobsLeaseExpired", rules)
        self.assertEqual(
            rules["SchoolWallJobsLeaseExpired"]["expr"],
            "schoolwall_jobs_running_lease_expired > 0",
        )

    def test_db_redis_rules_match_the_runbook_alert_targets(self):
        """DB/Redis 规则的阈值与持续时长必须照抄 runbook 的 DB/Redis 行。"""
        row = runbook_db_redis_row()
        percent = re.search(r"(\d+)%", row)
        minutes = re.findall(r"(\d+)\s*分钟", row)
        self.assertIsNotNone(percent, "runbook 的 DB/Redis 行必须写明连接池使用率阈值")
        self.assertTrue(minutes, "runbook 的 DB/Redis 行必须写明持续时长")
        threshold = int(percent.group(1)) / 100
        duration_minutes = int(minutes[0])

        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        self.assertIn("SchoolWallDbPoolPressure", rules)
        self.assertEqual(
            rules["SchoolWallDbPoolPressure"]["expr"],
            f"schoolwall_db_pool_usage_ratio > {threshold}",
        )
        self.assertEqual(str(rules["SchoolWallDbPoolPressure"]["for"]), f"{duration_minutes}m")

        self.assertIn("SchoolWallRedisFailures", rules)
        redis_expr = str(rules["SchoolWallRedisFailures"]["expr"])
        self.assertIn("schoolwall_redis_failures_total", redis_expr)
        self.assertIn("> 0", redis_expr)

    def test_db_redis_rules_only_use_metrics_the_application_exposes(self):
        """DB/Redis 规则引用的指标必须来自应用自身的 /metrics，而不是 exporter。"""
        exposed = guard.app_metric_names()
        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        for alert in ("SchoolWallDbPoolPressure", "SchoolWallRedisFailures"):
            referenced = guard.metric_names_in(str(rules[alert]["expr"]))
            self.assertTrue(referenced, f"{alert} 必须引用指标")
            for metric in referenced:
                self.assertIn(metric, exposed, f"{alert} 引用的 {metric} 必须由应用暴露")

    def test_backup_metrics_are_exposed_by_the_application(self):
        """备份侧信号必须真的可抓取，否则备份规则就是空转。"""
        exposed = guard.app_metric_names()
        for metric in BACKUP_METRICS:
            self.assertIn(metric, exposed, f"应用 /metrics 必须暴露 {metric}")

    def test_backup_rules_match_the_runbook_alert_targets(self):
        """备份规则的阈值与持续时长必须照抄 runbook 的备份行。

        备份行写的是「最新备份>26小时、失败增长」，没有给持续时长 —— 按仓库
        既有做法（jobs 行同样没给的两项）立即触发。WAL 归档的 30 分钟阈值来自
        pgBackRest，属人工与基础设施安排，不在这里冒充已覆盖。
        """
        row = runbook_backup_row()
        hours = re.findall(r"(\d+)\s*小时", row)
        self.assertTrue(hours, "runbook 的备份行必须写明最新备份的时效阈值")
        threshold = int(hours[0]) * 3600

        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        self.assertIn("SchoolWallBackupStale", rules)
        self.assertEqual(
            rules["SchoolWallBackupStale"]["expr"],
            f"schoolwall_backup_last_success_age_seconds > {threshold}",
        )
        self.assertEqual(str(rules["SchoolWallBackupStale"]["for"]), "0m")

        self.assertIn("SchoolWallBackupFailed", rules)
        failed_expr = str(rules["SchoolWallBackupFailed"]["expr"])
        self.assertIn("schoolwall_backup_last_attempt_succeeded", failed_expr)
        self.assertIn("schoolwall_backup_failures_total", failed_expr)
        self.assertIn("> 0", failed_expr)
        self.assertEqual(str(rules["SchoolWallBackupFailed"]["for"]), "0m")

        self.assertIn("SchoolWallBackupStatusUnknown", rules)
        self.assertEqual(
            rules["SchoolWallBackupStatusUnknown"]["expr"],
            "schoolwall_backup_status_collection_ok == 0",
        )
        self.assertEqual(str(rules["SchoolWallBackupStatusUnknown"]["for"]), "0m")

    def test_backup_rules_only_use_metrics_the_application_exposes(self):
        """备份规则引用的指标必须来自应用自身的 /metrics，而不是 exporter。"""
        exposed = guard.app_metric_names()
        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        for alert in ("SchoolWallBackupStale", "SchoolWallBackupFailed",
                      "SchoolWallBackupStatusUnknown"):
            referenced = guard.metric_names_in(str(rules[alert]["expr"]))
            self.assertTrue(referenced, f"{alert} 必须引用指标")
            for metric in referenced:
                self.assertIn(metric, exposed, f"{alert} 引用的 {metric} 必须由应用暴露")

    def test_wal_archive_alerts_are_not_claimed(self):
        """WAL 归档仍需 pgBackRest：仓库不得把它说成已经配置了规则。"""
        for rule in guard.load_rules(guard.DEFAULT_ALERTS):
            text = f"{rule.get('alert', '')} {rule.get('expr', '')}".lower()
            for marker in ("wal_", "archive", "pgbackrest"):
                self.assertNotIn(
                    marker, text,
                    f"{rule.get('alert')} 不得冒充已覆盖 WAL 归档（{marker}）",
                )

    def test_capacity_metrics_are_registered_exporter_metrics(self):
        """容量指标必须在守卫里显式登记为 node_exporter 暴露的指标。"""
        registered = guard.EXPORTER_SOURCES["node"]["metrics"]
        for metric in CAPACITY_METRICS:
            self.assertIn(metric, registered, f"{metric} 必须登记为 node_exporter 指标")
            self.assertIn(metric, guard.EXPORTER_METRICS)

    def test_capacity_rules_match_the_runbook_alert_targets(self):
        """容量规则的阈值与持续时长必须照抄 runbook 的容量/证书行。

        容量行写的是「磁盘<20%、内存>85% 10分钟、证书<14天」：磁盘与内存的阈值
        取自该行，10 分钟是内存那一项的持续时长；磁盘行表内没给持续时长，按仓库
        既有做法（jobs 行与备份行同样没给的项）立即触发。
        """
        row = runbook_capacity_row()
        percents = re.findall(r"(\d+)%", row)
        minutes = re.findall(r"(\d+)\s*分钟", row)
        self.assertGreaterEqual(len(percents), 2, "runbook 的容量行必须写明磁盘与内存阈值")
        self.assertTrue(minutes, "runbook 的容量行必须写明内存的持续时长")
        disk_threshold = int(percents[0]) / 100
        memory_threshold = int(percents[1]) / 100
        duration_minutes = int(minutes[0])

        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        self.assertIn("SchoolWallHostDiskSpaceLow", rules)
        disk_expr = str(rules["SchoolWallHostDiskSpaceLow"]["expr"])
        self.assertIn("node_filesystem_avail_bytes", disk_expr)
        self.assertIn("node_filesystem_size_bytes", disk_expr)
        self.assertIn(f"< {disk_threshold}", disk_expr)
        self.assertEqual(str(rules["SchoolWallHostDiskSpaceLow"]["for"]), "0m")

        self.assertIn("SchoolWallHostMemoryUsageHigh", rules)
        memory_expr = str(rules["SchoolWallHostMemoryUsageHigh"]["expr"])
        self.assertIn("node_memory_MemAvailable_bytes", memory_expr)
        self.assertIn("node_memory_MemTotal_bytes", memory_expr)
        self.assertIn(f"> {memory_threshold}", memory_expr)
        self.assertEqual(str(rules["SchoolWallHostMemoryUsageHigh"]["for"]),
                         f"{duration_minutes}m")

    def test_capacity_rules_only_use_node_exporter_metrics(self):
        """容量规则引用的指标必须来自 node_exporter，不是应用 /metrics 也不是别的。"""
        registered = guard.EXPORTER_SOURCES["node"]["metrics"]
        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        for alert in ("SchoolWallHostDiskSpaceLow", "SchoolWallHostMemoryUsageHigh"):
            referenced = guard.metric_names_in(str(rules[alert]["expr"]))
            self.assertTrue(referenced, f"{alert} 必须引用指标")
            for metric in referenced:
                self.assertIn(metric, registered,
                              f"{alert} 引用的 {metric} 必须由 node_exporter 暴露")

    def test_node_exporter_is_wired_into_the_monitoring_stack(self):
        """exporter 必须真的接进监控栈：compose 里有服务、prometheus.yml 里有抓取作业。"""
        compose = yaml.safe_load(
            guard.DEFAULT_COMPOSE.read_text(encoding="utf-8")) or {}
        services = compose.get("services") or {}
        self.assertIn("node-exporter", services, "监控栈里必须有 node-exporter 服务")
        service = services["node-exporter"]
        self.assertTrue(str(service.get("image", "")).startswith("prom/node-exporter:"))
        command = " ".join(str(part) for part in service.get("command") or [])
        self.assertIn("--web.listen-address=127.0.0.1:9100", command,
                      "exporter 只能监听回环地址")
        self.assertIn("--path.rootfs=/host", command,
                      "exporter 必须指向宿主机的根目录才能采到真实磁盘与内存")

        prometheus = yaml.safe_load(
            guard.DEFAULT_PROMETHEUS.read_text(encoding="utf-8")) or {}
        jobs = {job.get("job_name"): job
                for job in prometheus.get("scrape_configs") or []}
        self.assertIn("node-exporter", jobs, "prometheus.yml 必须有 node-exporter 抓取作业")
        targets = [
            target
            for entry in jobs["node-exporter"].get("static_configs") or []
            for target in entry.get("targets") or []
        ]
        self.assertIn("127.0.0.1:9100", targets)

        rules = guard.load_rules(guard.DEFAULT_ALERTS)
        self.assertEqual(guard.check_exporter_wiring(rules), {},
                         "仓库当前的规则不得引用没接线的 exporter")

    def test_exporter_wiring_problem_is_reported(self):
        """exporter 没接线时守卫必须指出问题，而不是默默放过。"""
        rules = guard.load_rules(guard.DEFAULT_ALERTS)
        with tempfile.TemporaryDirectory() as directory:
            compose = Path(directory) / "compose.monitoring.yml"
            compose.write_text("services:\n  prometheus: {}\n", encoding="utf-8")
            prometheus = Path(directory) / "prometheus.yml"
            prometheus.write_text(
                "scrape_configs:\n"
                "  - job_name: prometheus\n"
                "    static_configs: [{targets: [\"127.0.0.1:9090\"]}]\n",
                encoding="utf-8",
            )
            problems = guard.check_exporter_wiring(rules, compose, prometheus)
        self.assertIn("node", problems, "node_exporter 没接线必须被点名")
        self.assertTrue(any("node-exporter" in item for item in problems["node"]))

    def test_rule_referencing_an_unregistered_node_metric_is_rejected(self):
        """node_exporter 上不存在的指标名同样必须被拦下。"""
        with tempfile.TemporaryDirectory() as directory:
            alerts = Path(directory) / "alerts.yml"
            alerts.write_text(
                "groups:\n"
                "  - name: schoolwall\n"
                "    rules:\n"
                "      - alert: SchoolWallHostDiskSpaceLow\n"
                "        expr: node_filesystem_never_exposed_bytes > 0\n"
                "        for: 0m\n",
                encoding="utf-8",
            )
            result = self.run_guard(alerts)
        self.assertNotEqual(result.returncode, 0, "引用了没人暴露的指标必须立刻失败")
        self.assertIn("node_filesystem_never_exposed_bytes", result.stdout + result.stderr)

    def test_postgres_lock_metrics_are_registered_exporter_metrics(self):
        """锁等待指标必须在守卫里显式登记为 postgres_exporter 暴露的指标。"""
        registered = guard.EXPORTER_SOURCES["postgres"]["metrics"]
        for metric in POSTGRES_METRICS:
            self.assertIn(metric, registered, f"{metric} 必须登记为 postgres_exporter 指标")
            self.assertIn(metric, guard.EXPORTER_METRICS)

    def test_db_lock_wait_rules_match_the_runbook_alert_targets(self):
        """锁等待规则的阈值必须照抄 runbook 的 DB/Redis 行。

        该行原本只写「锁等待上升」、没有数值；收敛后的口径是「锁等待会话>0」与
        「死锁增长>0」。表内没给持续时长，按仓库既有做法立即触发。
        """
        wait_threshold, deadlock_threshold = runbook_lock_wait_thresholds()
        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}

        self.assertIn("SchoolWallDbLockWaitRising", rules)
        self.assertEqual(
            rules["SchoolWallDbLockWaitRising"]["expr"],
            'sum(pg_stat_activity_count{wait_event_type="Lock"}) > '
            f"{wait_threshold}",
        )
        self.assertEqual(str(rules["SchoolWallDbLockWaitRising"]["for"]), "0m")

        self.assertIn("SchoolWallDbDeadlockRising", rules)
        self.assertEqual(
            rules["SchoolWallDbDeadlockRising"]["expr"],
            f"increase(pg_stat_database_deadlocks[5m]) > {deadlock_threshold}",
        )
        self.assertEqual(str(rules["SchoolWallDbDeadlockRising"]["for"]), "0m")

    def test_db_lock_wait_rules_only_use_postgres_exporter_metrics(self):
        """锁等待规则引用的指标必须来自 postgres_exporter，不是应用 /metrics。"""
        registered = guard.EXPORTER_SOURCES["postgres"]["metrics"]
        rules = {rule.get("alert"): rule for rule in guard.load_rules(guard.DEFAULT_ALERTS)}
        for alert in ("SchoolWallDbLockWaitRising", "SchoolWallDbDeadlockRising"):
            referenced = guard.metric_names_in(str(rules[alert]["expr"]))
            self.assertTrue(referenced, f"{alert} 必须引用指标")
            for metric in referenced:
                self.assertIn(metric, registered,
                              f"{alert} 引用的 {metric} 必须由 postgres_exporter 暴露")

    def test_postgres_exporter_is_wired_into_the_monitoring_stack(self):
        """exporter 必须真的接进监控栈：compose 里有服务、prometheus.yml 里有抓取作业。"""
        compose = yaml.safe_load(
            guard.DEFAULT_COMPOSE.read_text(encoding="utf-8")) or {}
        services = compose.get("services") or {}
        self.assertIn("postgres-exporter", services, "监控栈里必须有 postgres-exporter 服务")
        service = services["postgres-exporter"]
        self.assertIn("postgres-exporter", str(service.get("image", "")))
        command = " ".join(str(part) for part in service.get("command") or [])
        self.assertIn("--web.listen-address=127.0.0.1:9187", command,
                      "exporter 只能监听回环地址")

        prometheus = yaml.safe_load(
            guard.DEFAULT_PROMETHEUS.read_text(encoding="utf-8")) or {}
        jobs = {job.get("job_name"): job
                for job in prometheus.get("scrape_configs") or []}
        self.assertIn("postgres-exporter", jobs, "prometheus.yml 必须有 postgres-exporter 抓取作业")
        targets = [
            target
            for entry in jobs["postgres-exporter"].get("static_configs") or []
            for target in entry.get("targets") or []
        ]
        self.assertIn("127.0.0.1:9187", targets)

        rules = guard.load_rules(guard.DEFAULT_ALERTS)
        self.assertEqual(guard.check_exporter_wiring(rules), {},
                         "仓库当前的规则不得引用没接线的 exporter")

    def test_monitoring_config_keeps_database_credentials_out_of_the_repository(self):
        """连接串与口令只走只读的运行时配置，仓库里不得出现口令。"""
        compose = guard.DEFAULT_COMPOSE.read_text(encoding="utf-8")
        self.assertIn("DATA_SOURCE_USER_FILE", compose,
                      "用户名必须来自只读挂载的运行时文件")
        self.assertIn("DATA_SOURCE_PASS_FILE", compose,
                      "口令必须来自只读挂载的运行时文件")
        self.assertNotIn("DATA_SOURCE_PASS=", compose, "仓库里不得写入口令")
        self.assertNotIn("DATA_SOURCE_USER=", compose, "仓库里不得写入监控账号")
        self.assertIsNone(
            re.search(r"postgresql://[^\s\"']*:[^\s\"'@]*@", compose),
            "连接串里不得带口令",
        )
        services = (yaml.safe_load(compose) or {}).get("services") or {}
        mounts = [str(mount) for mount in services["postgres-exporter"].get("volumes") or []]
        credential_mounts = [mount for mount in mounts if "/etc/postgres-exporter" in mount]
        self.assertTrue(credential_mounts, "凭据目录必须挂进容器")
        for mount in credential_mounts:
            self.assertTrue(mount.endswith(":ro"), "凭据目录只能以只读方式挂载")

    def test_rule_referencing_an_unregistered_postgres_metric_is_rejected(self):
        """postgres_exporter 上不存在的指标名同样必须被拦下。"""
        with tempfile.TemporaryDirectory() as directory:
            alerts = Path(directory) / "alerts.yml"
            alerts.write_text(
                "groups:\n"
                "  - name: schoolwall\n"
                "    rules:\n"
                "      - alert: SchoolWallDbLockWaitRising\n"
                "        expr: pg_stat_activity_never_exposed_count > 0\n"
                "        for: 0m\n",
                encoding="utf-8",
            )
            result = self.run_guard(alerts)
        self.assertNotEqual(result.returncode, 0, "引用了没人暴露的指标必须立刻失败")
        self.assertIn("pg_stat_activity_never_exposed_count", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
