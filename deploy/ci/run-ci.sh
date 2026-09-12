#!/usr/bin/env bash
# 服务器端 CI 入口：fetch 后仅在 origin/main 有新提交时跑一轮（供 systemd timer 调用）。
# - detached checkout origin/main：不动本地分支，跑完不残留状态
# - 无新提交时直接退出 0（timer 周期轮询成本极低）
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

git fetch origin main

LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse origin/main)"
if [ "$LOCAL" = "$REMOTE" ]; then
  echo "[run-ci] origin/main 无新提交（${LOCAL:0:7}），跳过本轮"
  exit 0
fi

echo "[run-ci] 检出新提交 ${LOCAL:0:7} → ${REMOTE:0:7}"
git checkout --detach "$REMOTE"

exec "$REPO/deploy/ci/ci.sh"
