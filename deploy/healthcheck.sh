#!/usr/bin/env bash
set -euo pipefail
BASE="${HEALTH_BASE_URL:-http://127.0.0.1:8000}"
curl --fail --silent --show-error --noproxy '*' --connect-timeout 2 --max-time 5 "$BASE/health/live" >/dev/null
curl --fail --silent --show-error --noproxy '*' --connect-timeout 2 --max-time 5 "$BASE/health/ready" >/dev/null
echo "[healthcheck] $(date -u +%FT%TZ) live and ready"
