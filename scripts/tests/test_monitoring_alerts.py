"""告警规则的可抓取性守卫回归。

`docs/production/runbook.md` 的「首发告警目标」表把 jobs 与 DB/Redis 列为首发
告警目标，但规则文件里如果引用了没人暴露的指标，规则就永远不触发（空转）：
值班人以为「已配置」，实际收不到信号。本用例既跑真实守卫脚本锁住仓库当前的
`deploy/monitoring/alerts.yml`，也用临时文件证明「引用了不可抓取指标的规则」
与「一个指标都没引用的规则」确实会被拦下，并锁住 jobs 与 DB/Redis 规则的
阈值与持续时长仍然照抄 runbook 的表。
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
