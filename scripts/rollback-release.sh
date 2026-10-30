#!/usr/bin/env bash
# Application-only rollback. Never automatically downgrade production data.
set -Eeuo pipefail
ROOT="${1:?deployment root}"
[[ "$ROOT" = /* && "$ROOT" != / && "$ROOT" != /opt ]] || exit 2
exec 9>"$ROOT/shared/release.lock"
flock -n 9 || exit 1
TARGET="$(realpath "${2:-$ROOT/previous}")"
case "$TARGET/" in "$ROOT/releases/"*) ;; *) echo "target is outside releases" >&2; exit 2;; esac
[[ -f "$TARGET/release.env" ]] || exit 2
EXTRA=()
[[ ! -f "$ROOT/shared/compose.backup.yml" ]] || EXTRA=(-f "$ROOT/shared/compose.backup.yml")
docker compose --project-name schoolwall --env-file "$ROOT/shared/.env" --env-file "$TARGET/release.env" \
  -f "$TARGET/deploy/docker-compose.prod.yml" "${EXTRA[@]}" up -d --no-build backend worker
PORT="$(sed -n 's/^API_PORT=//p' "$ROOT/shared/.env" | tail -1)"
REVISION="$(sed -n 's/^BUILD_REVISION=//p' "$TARGET/release.env")"
for attempt in $(seq 1 45); do
  if curl -fsS --max-time 3 "http://127.0.0.1:${PORT:-8000}/health/ready" >/dev/null \
    && curl -fsS --max-time 3 "http://127.0.0.1:${PORT:-8000}/health/live" | python3 -c 'import json,sys; assert json.load(sys.stdin).get("revision")==sys.argv[1]' "$REVISION"; then
    ln -s "$TARGET" "$ROOT/current.next"
    mv -Tf "$ROOT/current.next" "$ROOT/current"
    echo "application rollback ready; database schema retained"
    exit 0
  fi
  sleep 2
done
echo "rollback health check failed; preserve evidence and escalate" >&2
exit 1
