#!/usr/bin/env bash
# SchoolWall 后端健康检查脚本（供外部 cron/监控调用）
# 用法：*/5 * * * * /opt/schoolwall/deploy/healthcheck.sh
set -euo pipefail
URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
if curl -fsS --noproxy '*' --max-time 5 "$URL" | grep -q '"status":"ok"'; then
  exit 0
fi
echo "[healthcheck] $(date '+%F %T') backend unhealthy: $URL"
exit 1
