#!/usr/bin/env bash
# Logical emergency backup; production PITR uses pgBackRest (backup/README.md).
set -euo pipefail
cd "$(dirname "$0")"
BACKUP_DIR="${BACKUP_DIR:-backups}"
KEEP_BACKUPS="${KEEP_BACKUPS:-14}"
[[ "$KEEP_BACKUPS" =~ ^[1-9][0-9]*$ ]] || { echo "KEEP_BACKUPS must be positive" >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
umask 077
STAMP="$(date -u +%Y-%m-%d_%H%M%S)"
OUT="$BACKUP_DIR/ey_wall_${STAMP}.sql.gz"
TMP="${OUT}.partial"
trap 'rm -f -- "$TMP"' EXIT
docker compose -f docker-compose.prod.yml --env-file "${APP_ENV_FILE:-.env.prod}" exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d ey_wall' | gzip >"$TMP"
gzip --test "$TMP"
mv -- "$TMP" "$OUT"
python3 backup_retention.py "$BACKUP_DIR" "$KEEP_BACKUPS"
echo "[backup] $(date -u +%FT%TZ) -> $OUT (logical backup; restore not yet proved)"
