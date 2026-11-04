"""读取逻辑备份的状态文件，把备份新鲜度与备份失败变成可抓取的信号。

`deploy/backup.sh` 每次尝试（成功或失败）都把结果写进
`<状态目录>/backup_status.json`：里面只有时间戳与计数，**不含备份路径、对象
存储密钥、连接串或备份内容**。本模块只读那个文件，输出：

  * 距最近一次成功备份的秒数（时长）；
  * 最近一次备份尝试是否成功（布尔）；
  * 累计失败次数（计数）；
  * 状态是否读到了（布尔）。

读不到（路径没配、文件不存在、内容坏了）一律按「未知」记，不抛异常 ——
`/metrics` 是 Prometheus 的抓取入口，不能因为备份状态读不到就整个返回 500，
把这一轮全部指标一起抹掉。

WAL 归档、PITR 与异机备份不在这里冒充已覆盖：那些信号来自 pgBackRest，
属人工与基础设施安排（见 deploy/backup/README.md）。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("schoolwall.metrics")

# 状态读不到时「距最近一次成功备份的秒数」按 -1 记：负值表示未知，
# 不会被「>26 小时」的阈值误判成过期。
UNKNOWN_AGE_SECONDS = -1.0


@dataclass(frozen=True)
class BackupStatus:
    """一次备份状态的快照。"""

    readable: bool
    last_success_age_seconds: float
    last_attempt_succeeded: bool
    failures: int


def _parse_timestamp(value: object) -> datetime | None:
    """解析状态文件里的时间戳；格式不对就当没有。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def read_backup_status(path: str | Path, now: datetime | None = None) -> BackupStatus:
    """读备份状态文件；读不到或内容坏了就返回「未知」状态。"""
    unknown = BackupStatus(
        readable=False,
        last_success_age_seconds=UNKNOWN_AGE_SECONDS,
        last_attempt_succeeded=False,
        failures=0,
    )
    if not path:
        return unknown
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return unknown
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("backup status file is not valid json")
        return unknown
    if not isinstance(data, dict):
        return unknown

    moment = now or datetime.now(timezone.utc)
    last_success_at = _parse_timestamp(data.get("last_success_at"))
    if last_success_at is None:
        age = UNKNOWN_AGE_SECONDS
    else:
        age = max(0.0, (moment - last_success_at).total_seconds())

    failures = data.get("failures")
    failures = failures if isinstance(failures, int) and not isinstance(failures, bool) else 0
    return BackupStatus(
        readable=True,
        last_success_age_seconds=age,
        last_attempt_succeeded=data.get("last_attempt_ok") is True,
        failures=max(0, failures),
    )
