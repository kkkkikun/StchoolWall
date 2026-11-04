#!/usr/bin/env python3
"""告警规则的可抓取性守卫。

`deploy/monitoring/alerts.yml` 里的表达式如果引用了没人暴露的指标，规则就永远
不触发（空转）：值班人以为「已配置」，实际收不到任何信号。本脚本把每条规则
表达式里引用的指标名与「真实可抓取的指标名集合」逐条比对：

  * 应用自身在 /metrics 暴露的指标 —— prometheus_client 默认 registry 渲染出的
    名字（backend/app/metrics.py 在那里注册），/metrics 用 generate_latest()
    渲染的是同一个 registry；
  * 既定 exporter 暴露的指标 —— blackbox_exporter（deploy/monitoring/blackbox.yml
    的 http_2xx 模块）、node_exporter（deploy/monitoring/compose.monitoring.yml 的
    node-exporter 服务，磁盘与内存信号）与 Prometheus 自带的 up。

反过来，表达式里一个指标都没引用（例如 `1 > 0`）的规则同样要拦下：这种规则
要么恒真、要么恒假，与告警目标无关。

指标登记了还不够：exporter 没部署、没被 Prometheus 抓取，规则照样收不到信号。
所以每个 exporter 同时登记它必须被接线的地方（compose 里的服务、prometheus.yml
里的抓取作业），规则引用到的 exporter 没接线同样非零退出。

用法：
    python scripts/check_monitoring_alerts.py [alerts.yml]

退出码 0 表示每条规则引用的指标都真的可抓取、且用到的 exporter 都接进了监控栈；
1 表示存在空转的规则或没接线的 exporter。

依赖：PyYAML 随 backend 的 uvicorn[standard] 一并安装（scripts/tests 里已有
同样的用法），应用指标面需要 backend 的运行依赖。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALERTS = ROOT / "deploy/monitoring/alerts.yml"
DEFAULT_COMPOSE = ROOT / "deploy/monitoring/compose.monitoring.yml"
DEFAULT_PROMETHEUS = ROOT / "deploy/monitoring/prometheus.yml"

# 既定 exporter 暴露、应用自己不会暴露的指标 —— 按 exporter 显式登记：
#   prometheus —— up，每个抓取目标都有
#   blackbox  —— blackbox_exporter 的 http_2xx 模块（deploy/monitoring/blackbox.yml）
#   node      —— node_exporter（deploy/monitoring/compose.monitoring.yml 的
#                node-exporter 服务），提供磁盘可用空间与内存使用率
# 登记的是「这个 exporter 真实会暴露的指标名」：规则引用了没人暴露的指标就是空转。
# 每个 exporter 还登记它必须被接线的地方：指标名登记了、exporter 却没部署或没被抓取，
# 规则仍然是空转，所以那两处也对齐检查。
EXPORTER_SOURCES = {
    "prometheus": {
        "compose_service": None,          # up 由任何抓取作业产出，不绑定具体服务
        "prometheus_job": "any",
        "metrics": frozenset({"up"}),
    },
    "blackbox": {
        "compose_service": "blackbox",
        "prometheus_job": "schoolwall-probes",
        "metrics": frozenset({
            "probe_success",
            "probe_duration_seconds",
            "probe_ssl_earliest_cert_expiry",
        }),
    },
    "node": {
        "compose_service": "node-exporter",
        "prometheus_job": "node-exporter",
        "metrics": frozenset({
            "node_filesystem_avail_bytes",
            "node_filesystem_size_bytes",
            "node_memory_MemAvailable_bytes",
            "node_memory_MemTotal_bytes",
        }),
    },
}
EXPORTER_METRICS = frozenset().union(
    *(source["metrics"] for source in EXPORTER_SOURCES.values())
)

# PromQL 的关键字不是指标名。
_PROMQL_KEYWORDS = {
    "and", "or", "unless", "by", "without", "on", "ignoring", "group_left", "group_right",
    "offset", "bool", "start", "end", "keep_last", "atan2",
}

_LABEL_SELECTOR = re.compile(r"\{[^{}]*\}")
_RANGE_SELECTOR = re.compile(r"\[[^\[\]]*\]")
_GROUPING_CLAUSE = re.compile(r"\b(?:by|without|on|ignoring|group_left|group_right)\s*\([^()]*\)")
_IDENTIFIER = re.compile(r"[a-zA-Z_:][a-zA-Z0-9_:]*")
_SAMPLE_NAME = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^}]*\})?\s")
_TYPE_LINE = re.compile(r"^#\s+TYPE\s+([a-zA-Z_:][a-zA-Z0-9_:]*)\s")


def metric_names_in(expr: str) -> set[str]:
    """取出表达式里引用的指标名（函数名与关键字不算）。"""
    text = _LABEL_SELECTOR.sub(" ", expr)
    text = _RANGE_SELECTOR.sub(" ", text)
    text = _GROUPING_CLAUSE.sub(" ", text)
    names = set()
    for match in _IDENTIFIER.finditer(text):
        name = match.group(0)
        if name in _PROMQL_KEYWORDS:
            continue
        if text[match.end():].lstrip().startswith("("):
            continue  # 函数调用，例如 rate(...) / histogram_quantile(...)
        names.add(name)
    return names


def load_rules(path: Path) -> list[dict]:
    """读出规则文件里的全部告警规则。"""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = []
    for group in document.get("groups") or []:
        for rule in group.get("rules") or []:
            rules.append(rule)
    return rules


def _names_in_exposition(text: str) -> set[str]:
    """取 exposition 文本里出现的指标名（与抓取到的字面一致）。

    带标签的指标在没有样本时只出现在 "# TYPE" 行里，所以两处都要收。
    """
    names = set()
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("#"):
            match = _TYPE_LINE.match(line)
            if match:
                names.add(match.group(1))
            continue
        match = _SAMPLE_NAME.match(line)
        if match:
            names.add(match.group(1))
    return names


def _series_names(metric) -> set[str]:
    """一个 metric family 在 Prometheus 里对应的可抓取序列名。

    直方图家族 "x" 的序列是 x_bucket / x_sum / x_count，计数器家族 "x_total"
    的序列是 x_total —— 这些派生名只在真正有样本后才出现在抓取文本里，
    所以按 Prometheus 的数据模型显式补齐。
    """
    names = {metric.name}
    if metric.type == "counter":
        names.add(metric.name if metric.name.endswith("_total") else f"{metric.name}_total")
    elif metric.type == "histogram":
        names.update({f"{metric.name}_bucket", f"{metric.name}_sum", f"{metric.name}_count"})
    elif metric.type == "summary":
        names.update({f"{metric.name}_sum", f"{metric.name}_count"})
    return names


def app_metric_names() -> set[str]:
    """应用 /metrics 实际暴露的指标名（含各派生序列名）。"""
    backend = str(ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from prometheus_client import REGISTRY, generate_latest
    import app.metrics  # noqa: F401  # 导入即把应用指标注册到默认 registry

    names = _names_in_exposition(generate_latest().decode("utf-8"))
    for metric in REGISTRY.collect():
        names.update(_series_names(metric))
    return names


def check_rules(rules: list[dict], known: set[str]) -> dict[str, list[str]]:
    """返回「规则名 -> 无人暴露的指标名列表」，空字典表示全部可抓取。

    除了「引用了没人暴露的指标」，还拦一种更隐蔽的空转：表达式里根本没引用
    任何指标（例如 `1 > 0`）—— 这种规则要么恒真、要么恒假，与告警目标无关。
    """
    problems: dict[str, list[str]] = {}
    for index, rule in enumerate(rules):
        name = rule.get("alert") or f"<rule #{index + 1} without an alert name>"
        expr = rule.get("expr")
        if not expr:
            problems.setdefault(name, []).append("<rule without an expr>")
            continue
        referenced = metric_names_in(str(expr))
        if not referenced:
            problems.setdefault(name, []).append("<rule that references no metric>")
            continue
        unknown = sorted(referenced - known)
        if unknown:
            problems.setdefault(name, []).extend(unknown)
    return problems


def compose_services(path: Path) -> set[str]:
    """监控栈 compose 文件里定义的服务名。"""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return set((document.get("services") or {}).keys())


def prometheus_jobs(path: Path) -> set[str]:
    """Prometheus 配置里的抓取作业名。"""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(job.get("job_name"))
        for job in document.get("scrape_configs") or []
        if job.get("job_name")
    }


def referenced_metrics(rules: list[dict]) -> set[str]:
    """全部规则表达式里引用到的指标名。"""
    names: set[str] = set()
    for rule in rules:
        expr = rule.get("expr")
        if expr:
            names |= metric_names_in(str(expr))
    return names


def check_exporter_wiring(
    rules: list[dict],
    compose_path: Path = DEFAULT_COMPOSE,
    prometheus_path: Path = DEFAULT_PROMETHEUS,
) -> dict[str, list[str]]:
    """返回「exporter 名 -> 没接线的说明」，空字典表示用到的 exporter 都接上了。

    只检查规则真正引用到的 exporter：没人引用的 exporter 不必在场。检查两处 ——
    compose 里的服务（exporter 得真的部署）与 prometheus.yml 里的抓取作业
    （Prometheus 得真的去抓）；两处缺一，规则都是空转。
    """
    referenced = referenced_metrics(rules)
    services = compose_services(compose_path)
    jobs = prometheus_jobs(prometheus_path)

    problems: dict[str, list[str]] = {}
    for name, source in EXPORTER_SOURCES.items():
        if not source["metrics"] & referenced:
            continue
        missing = []
        service = source.get("compose_service")
        if service and service not in services:
            missing.append(f"compose.monitoring.yml 里没有 {service} 服务")
        job = source.get("prometheus_job")
        if job == "any":
            if not jobs:
                missing.append("prometheus.yml 里没有任何抓取作业")
        elif job and job not in jobs:
            missing.append(f"prometheus.yml 里没有 {job} 抓取作业")
        if missing:
            problems[name] = missing
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验告警规则引用的指标都真的可抓取")
    parser.add_argument("alerts", nargs="?", default=str(DEFAULT_ALERTS),
                        help="告警规则文件（默认 deploy/monitoring/alerts.yml）")
    args = parser.parse_args(argv)
    path = Path(args.alerts)
    if not path.exists():
        print(f"alert rules file not found: {path}")
        return 1

    rules = load_rules(path)
    known = app_metric_names() | EXPORTER_METRICS
    problems = check_rules(rules, known)
    if problems:
        print(f"alert rules reference metrics nobody exposes: {path}")
        for name, unknown in problems.items():
            print(f"  {name}: {', '.join(unknown)}")
        return 1
    wiring = check_exporter_wiring(rules)
    if wiring:
        print("alert rules reference exporters that are not wired into the monitoring stack:")
        for name, missing in wiring.items():
            print(f"  {name}: {'; '.join(missing)}")
        return 1
    print(f"monitoring alerts validated: {len(rules)} rules, "
          f"all referenced metrics are scrapeable ({len(known)} known metric names)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
