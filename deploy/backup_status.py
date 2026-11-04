#!/usr/bin/env python3
"""记录逻辑备份的结果，让备份新鲜度与备份失败变成可抓取的信号。

`deploy/backup.sh` 每次尝试（成功或失败）都调用本脚本，把结果写进状态文件
`<目录>/backup_status.json`。文件里只有时间戳与计数 —— **不含备份路径、对象
存储密钥、连接串或备份内容**，因此可以只读挂进后端容器。

应用侧（`backend/app/backup_status.py`）读同一个文件，把「距最近一次成功备份
的秒数」「最近一次尝试是否成功」「累计失败次数」暴露成 Prometheus 指标，
`deploy/monitoring/alerts.yml` 再按 `docs/production/runbook.md`「首发告警目标」
表的备份行接上告警规则（最新备份 >26 小时、备份失败增长）。

用法：
    python3 backup_status.py record --dir <状态目录> --outcome success|failure
    python3 backup_status.py show --dir <状态目录>

`record` 永远以 0 退出（写状态失败只打印一行告警）：备份本身成功与否由备份
脚本决定，状态文件写不进去不该反过来把备份判成失败 —— 那会让值班人拿到一个
假的「备份失败」。
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FILE_NAME = "backup_status.json"
FILE_VERSION = 1
OUTCOMES = ("success", "failure")

# 状态目录与状态文件的权限：文件里没有机密，但要让后端容器（uid 10001）能读到，
# 所以目录给 0755、文件给 0644；备份产物本身仍是 0600，不受这里影响。
DIRECTORY_MODE = 0o755
FILE_MODE = 0o644


def status_path(directory: Path) -> Path:
    """状态文件路径。"""
    return Path(directory) / FILE_NAME


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_state() -> dict:
    return {
        "version": FILE_VERSION,
        "attempts": 0,
        "failures": 0,
        "last_attempt_at": None,
        "last_attempt_ok": None,
        "last_success_at": None,
    }


def read_state(directory: Path) -> dict:
    """读回上一次的状态；文件不存在或内容坏了就按空状态算（不抛）。"""
    state = _empty_state()
    try:
        raw = status_path(directory).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return state
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return state
    if not isinstance(data, dict):
        return state
    for key in ("attempts", "failures"):
        value = data.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            state[key] = value
    for key in ("last_attempt_at", "last_success_at"):
        value = data.get(key)
        if isinstance(value, str):
            state[key] = value
    ok = data.get("last_attempt_ok")
    if isinstance(ok, bool):
        state["last_attempt_ok"] = ok
    return state


def record(directory: Path, outcome: str, moment: datetime | None = None) -> dict:
    """把一次备份尝试的结果写进状态文件，返回写后的状态。"""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    directory = Path(directory)
    created = not directory.exists()
    directory.mkdir(parents=True, exist_ok=True)
    if created:
        try:
            os.chmod(directory, DIRECTORY_MODE)
        except OSError:
            pass
    moment = moment or datetime.now(timezone.utc)
    state = read_state(directory)
    state["version"] = FILE_VERSION
    state["attempts"] += 1
    state["last_attempt_at"] = _stamp(moment)
    state["last_attempt_ok"] = outcome == "success"
    if outcome == "success":
        state["last_success_at"] = state["last_attempt_at"]
    else:
        state["failures"] += 1
    _write_state(directory, state)
    return state


def _write_state(directory: Path, state: dict) -> None:
    """原子写状态文件：先写临时文件再改名，抓取方不会读到半个文件。"""
    path = status_path(directory)
    handle, temporary = tempfile.mkstemp(dir=str(directory), prefix=".backup_status.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
        os.chmod(temporary, FILE_MODE)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="记录或查看逻辑备份的状态")
    parser.add_argument("command", choices=("record", "show"))
    parser.add_argument("--dir", required=True, help="状态目录（状态文件写在里面）")
    parser.add_argument("--outcome", choices=OUTCOMES, help="record 时的结果")
    args = parser.parse_args(argv)
    directory = Path(args.dir)
    if args.command == "record":
        if not args.outcome:
            parser.error("record 需要 --outcome")
        state = record(directory, args.outcome)
    else:
        state = read_state(directory)
    print(json.dumps(state, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
