#!/usr/bin/env bash
# Logical emergency backup; production PITR uses pgBackRest (backup/README.md).
set -euo pipefail
cd "$(dirname "$0")"
BACKUP_DIR="${BACKUP_DIR:-backups}"
BACKUP_STATUS_DIR="${BACKUP_STATUS_DIR:-backup-status}"
KEEP_BACKUPS="${KEEP_BACKUPS:-14}"
[[ "$KEEP_BACKUPS" =~ ^[1-9][0-9]*$ ]] || { echo "KEEP_BACKUPS must be positive" >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
umask 077
STAMP="$(date -u +%Y-%m-%d_%H%M%S)"
OUT="$BACKUP_DIR/ey_wall_${STAMP}.sql.gz"
TMP="${OUT}.partial"

# 每次尝试都把结果写进状态文件：应用 /metrics 据此暴露备份新鲜度与备份失败信号
# （backend/app/backup_status.py、deploy/monitoring/alerts.yml）。状态文件里只有
# 时间戳与计数，没有备份路径、对象存储密钥、连接串或备份内容。
record_status() {
  python3 backup_status.py record --dir "$BACKUP_STATUS_DIR" --outcome "$1" \
    || echo "[backup] could not record the backup status" >&2
}

on_exit() {
  local code=$?
  rm -f -- "$TMP"
  if [[ $code -ne 0 ]]; then
    record_status failure
  fi
  exit "$code"
}
trap on_exit EXIT

docker compose -f docker-compose.prod.yml --env-file "${APP_ENV_FILE:-.env.prod}" exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d ey_wall' | gzip >"$TMP"
gzip --test "$TMP"
mv -- "$TMP" "$OUT"
python3 backup_retention.py "$BACKUP_DIR" "$KEEP_BACKUPS"
record_status success
echo "[backup] $(date -u +%FT%TZ) -> $OUT (logical backup; restore not yet proved)"
