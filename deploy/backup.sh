#!/usr/bin/env bash
# SchoolWall 数据库备份脚本
# 用法：sudo crontab -e
#   0 3 * * * /opt/schoolwall/deploy/backup.sh >> /var/log/schoolwall-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")"
STAMP="$(date +%F_%H%M%S)"
OUT="backups/ey_wall_${STAMP}.sql.gz"
mkdir -p backups
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db   pg_dump -U "${DB_USER:-eywall}" ey_wall | gzip > "$OUT"
# 只保留最近 14 份
ls -1 backups/ey_wall_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
echo "[backup] $(date '+%F %T') -> $OUT"
