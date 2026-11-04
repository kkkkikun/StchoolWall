#!/usr/bin/env python3
"""告警规则的可抓取性守卫。

`deploy/monitoring/alerts.yml` 里的表达式如果引用了没人暴露的指标，规则就永远
不触发（空转）：值班人以为「已配置」，实际收不到任何信号。本脚本把每条规则
表达式里引用的指标名与「真实可抓取的指标名集合」逐条比对：

  * 应用自身在 /metrics 暴露的指标 —— prometheus_client 默认 registry 渲染出的
    名字（backend/app/metrics.py 在那里注册），/metrics 用 generate_latest()
    渲染的是同一个 registry；
  * 既定 exporter 暴露的指标 —— blackbox_exporter（deploy/monitoring/blackbox.yml
    的 http_2xx 模块）与 Prometheus 自带的 up。

反过来，表达式里一个指标都没引用（例如 `1 > 0`）的规则同样要拦下：这种规则
要么恒真、要么恒假，与告警目标无关。

用法：
    python scripts/check_monitoring_alerts.py [alerts.yml]

退出码 0 表示每条规则引用的指标都真的可抓取；1 表示存在空转的规则。

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

# 既定 exporter 暴露、应用自己不会暴露的指标：
#   up                          —— Prometheus 自身，每个抓取目标都有
#   probe_*                     —— blackbox_exporter 的 http_2xx 模块（deploy/monitoring/blackbox.yml）
EXPORTER_METRICS = {
    "up",
    "probe_success",
    "probe_duration_seconds",
    "probe_ssl_earliest_cert_expiry",
}

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
    print(f"monitoring alerts validated: {len(rules)} rules, "
          f"all referenced metrics are scrapeable ({len(known)} known metric names)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
