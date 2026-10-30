#!/usr/bin/env bash
# Run by one release controller per host. Only backward-compatible DB changes are eligible.
set -Eeuo pipefail
ROOT="${1:?absolute deployment root}"
SOURCE="${2:?extracted release directory}"
[[ "$ROOT" = /* && "$ROOT" != / && "$ROOT" != /opt ]] || { echo "unsafe deployment root" >&2; exit 2; }
SOURCE="$(realpath "$SOURCE")"
mkdir -p "$ROOT/releases" "$ROOT/shared"
exec 9>"$ROOT/shared/release.lock"
flock -n 9 || { echo "another release holds the lock" >&2; exit 1; }
mapfile -t META < <(python3 - "$SOURCE/manifest.json" <<'PY'
import json,re,sys
m=json.load(open(sys.argv[1]))
assert re.fullmatch(r"[a-f0-9]{40}", m["revision"]), "invalid revision"
assert re.fullmatch(r"ghcr.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}", m["backend_image"]), "digest required"
print(m["revision"]); print(m["backend_image"])
PY
)
[[ "${#META[@]}" = 2 ]] || { echo "invalid manifest" >&2; exit 2; }
REVISION="${META[0]}"
IMAGE="${META[1]}"
RELEASE="$ROOT/releases/$REVISION"
APP_ENV_FILE="$ROOT/shared/.env"
[[ -r "$APP_ENV_FILE" ]] || { echo "missing shared/.env" >&2; exit 2; }
# Production is the default. Staging must explicitly set DEPLOY_ENVIRONMENT=staging in shared/.env.
DEPLOY_ENVIRONMENT="$(sed -n 's/^DEPLOY_ENVIRONMENT=//p' "$APP_ENV_FILE" | tail -1)"
if [[ "$DEPLOY_ENVIRONMENT" != staging ]]; then
  python3 - "$ROOT/shared/release-gates.json" "$REVISION" <<'PY'
import json,sys
g=json.load(open(sys.argv[1]))
assert g.get("production_approved") is True, "production approval absent"
assert g.get("revision") == sys.argv[2], "approval is for another revision"
assert g.get("reviewer") and g.get("reviewed_at"), "named release review required"
assert all(g.get("evidence",{}).get(k) for k in ("G0","G1","G2","G3","G4")), "missing gate evidence"
PY
fi
if [[ -e "$RELEASE" ]]; then
  cmp --silent "$SOURCE/manifest.json" "$RELEASE/manifest.json" || { echo "revision already exists with another manifest" >&2; exit 2; }
else
  mkdir "$RELEASE"
  cp -a "$SOURCE/." "$RELEASE/"
fi
printf 'BACKEND_IMAGE=%s\nBUILD_REVISION=%s\nAPP_ENV_FILE=%s\n' "$IMAGE" "$REVISION" "$APP_ENV_FILE" > "$RELEASE/release.env"
PREVIOUS="$(readlink -f "$ROOT/current" 2>/dev/null || true)"
compose_at() {
  local release="$1"; shift
  local extra=()
  [[ ! -f "$ROOT/shared/compose.backup.yml" ]] || extra=(-f "$ROOT/shared/compose.backup.yml")
  docker compose --project-name schoolwall --env-file "$APP_ENV_FILE" --env-file "$release/release.env" \
    -f "$release/deploy/docker-compose.prod.yml" "${extra[@]}" "$@"
}
recover() {
  local status=$?
  trap - ERR
  if [[ -n "$PREVIOUS" && -f "$PREVIOUS/release.env" ]]; then
    echo "release failed; restoring previous application image (DB is not downgraded)" >&2
    compose_at "$PREVIOUS" up -d --no-build backend worker || true
  else
    compose_at "$RELEASE" stop backend worker || true
  fi
  exit "$status"
}
trap recover ERR
compose_at "$RELEASE" pull backend worker migrate
compose_at "$RELEASE" up -d db redis
# Worker is stopped before the only migration job. API remains on the prior compatible schema.
compose_at "$RELEASE" stop worker
compose_at "$RELEASE" run --rm migrate
compose_at "$RELEASE" up -d --no-build backend worker
API_PORT="$(sed -n 's/^API_PORT=//p' "$APP_ENV_FILE" | tail -1)"
API_PORT="${API_PORT:-8000}"
ready=false
for attempt in $(seq 1 45); do
  if curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:$API_PORT/health/ready" >/dev/null 2>&1 \
    && curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:$API_PORT/health/live" \
       | python3 -c 'import json,sys; assert json.load(sys.stdin).get("revision")==sys.argv[1]' "$REVISION" \
    && [[ -n "$(compose_at "$RELEASE" ps --status running -q worker)" ]]; then
    ready=true
    break
  fi
  sleep 2
done
[[ "$ready" = true ]]
# The web release switches atomically after the matching backend is ready.
ln -s "$RELEASE" "$ROOT/current.next"
mv -Tf "$ROOT/current.next" "$ROOT/current"
if [[ -n "$PREVIOUS" && "$PREVIOUS" != "$RELEASE" ]]; then
  ln -sfn "$PREVIOUS" "$ROOT/previous"
fi
trap - ERR
printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$REVISION" "$IMAGE" >> "$ROOT/shared/releases.log"
echo "release ready: $REVISION; external smoke and canary approval remain required"
