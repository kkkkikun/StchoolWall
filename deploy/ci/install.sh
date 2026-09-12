#!/usr/bin/env bash
# 一键安装服务器 CI：系统级 systemd oneshot service + 每小时 timer。
#
# 前提：
#   1. 仓库已 clone 到本机（私有仓需凭证，见 README.md §2）
#   2. docker + compose v2 已装，当前用户在 docker 组（能跑 docker compose 即可）
#
# 用法（在仓库根或任意位置执行）：
#   ./deploy/ci/install.sh            # 安装并启用 timer
#   ./deploy/ci/install.sh --run      # 安装后立即手动触发一轮
set -euo pipefail

# root 允许（常见单用途服务器全 root 操作）：凭证与 service 同为 root，上下文自洽。
# 运行身份（root 或 docker 组成员）以 docker info 实测为准，service 将以同一身份运行。
if ! docker info >/dev/null 2>&1; then
  echo "当前用户无权操作 docker（需 root 或 docker 组成员）" >&2
  exit 1
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_USER="$(id -un)"

command -v docker >/dev/null || { echo "未检测到 docker，请先安装" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "未检测到 docker compose v2" >&2; exit 1; }

echo "[install] 仓库路径：$REPO（service 将以此为准，勿移动目录）"

sudo tee /etc/systemd/system/schoolwall-ci.service >/dev/null <<EOF
[Unit]
Description=SchoolWall CI pipeline (docker-based, oneshot)

[Service]
Type=oneshot
User=$RUN_USER
WorkingDirectory=$REPO
ExecStart=$REPO/deploy/ci/run-ci.sh
# 全管线含依赖安装与三端构建，上限 30 分钟
TimeoutStartSec=1800
EOF

sudo tee /etc/systemd/system/schoolwall-ci.timer >/dev/null <<EOF
[Unit]
Description=Run SchoolWall CI hourly when origin/main advances

[Timer]
OnCalendar=hourly
RandomizedDelaySec=300
Persistent=true

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now schoolwall-ci.timer

echo "[install] 已启用："
systemctl list-timers schoolwall-ci.timer --no-pager || true

if [ "${1:-}" = "--run" ]; then
  echo "[install] 手动触发一轮…"
  sudo systemctl start schoolwall-ci.service
  journalctl -u schoolwall-ci.service -f
fi
