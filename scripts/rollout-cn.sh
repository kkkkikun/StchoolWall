#!/usr/bin/env bash
# Release controller for the CN staging host sharing its Caddy with OpenFeedback.
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
REVISION="${META[0]}"
IMAGE="${META[1]}"
RELEASE="$ROOT/releases/$REVISION"
APP_ENV_FILE="$ROOT/shared/.env"
[[ -r "$APP_ENV_FILE" ]] || { echo "missing shared/.env" >&2; exit 1; }
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
  cmp --silent "$SOURCE/manifest.json" "$RELEASE/manifest.json" || { echo "revision already exists with another manifest" >&2; exit 1; }
else
  mkdir "$RELEASE"
  cp -a "$SOURCE/." "$RELEASE/"
fi
PREVIOUS_IMAGE="$(docker inspect schoolwall-cn-backend-1 --format '{{.Config.Image}}' 2>/dev/null || true)"
PREVIOUS_REVISION="$(docker exec schoolwall-cn-backend-1 python -c 'import urllib.request,json; print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/live"))["revision"])' 2>/dev/null || true)"
CHANGED_WEB=()

compose_at() {
  local image="$1" revision="$2"; shift 2
  BACKEND_IMAGE="$image" BUILD_REVISION="$revision" \
    docker compose --project-name schoolwall-cn --env-file "$APP_ENV_FILE" \
    -f "$RELEASE/deploy/docker-compose.cn.yml" "$@"
}

restore_web() {
  for area in "${CHANGED_WEB[@]}"; do
    [[ ! -d "$ROOT/web/$area" ]] || mv -f "$ROOT/web/$area" "$ROOT/web/$area.failed-$REVISION"
    [[ ! -d "$ROOT/web/$area.before-$REVISION" ]] || mv -f "$ROOT/web/$area.before-$REVISION" "$ROOT/web/$area"
  done
}

recover() {
  local status=$?
  trap - ERR
  echo "release failed; restoring previous application" >&2
  if [[ -n "$PREVIOUS_IMAGE" && -n "$PREVIOUS_REVISION" ]]; then
    compose_at "$PREVIOUS_IMAGE" "$PREVIOUS_REVISION" up -d --no-build backend worker || true
  else
    compose_at "$IMAGE" "$REVISION" stop backend worker || true
  fi
  restore_web
  exit "$status"
}
trap recover ERR

compose_at "$IMAGE" "$REVISION" pull backend worker migrate
compose_at "$IMAGE" "$REVISION" up -d db redis
compose_at "$IMAGE" "$REVISION" stop worker
compose_at "$IMAGE" "$REVISION" run --rm migrate
compose_at "$IMAGE" "$REVISION" up -d --no-build backend worker

ready=false
for _ in $(seq 1 45); do
  backend_id="$(compose_at "$IMAGE" "$REVISION" ps -q backend 2>/dev/null || true)"
  if [[ -n "$backend_id" && "$(docker inspect -f '{{.State.Health.Status}}' "$backend_id" 2>/dev/null || true)" == healthy ]]; then
    actual="$(docker exec "$backend_id" python -c 'import urllib.request,json; print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/live"))["revision"])' 2>/dev/null || true)"
    if [[ "$actual" == "$REVISION" && -n "$(compose_at "$IMAGE" "$REVISION" ps --status running -q worker)" ]]; then
      ready=true
      break
    fi
  fi
  sleep 2
done
[[ "$ready" == true ]]

for area in h5 admin; do
  [[ ! -d "$RELEASE/web/$area" ]] && continue
  if diff -qr "$ROOT/web/$area" "$RELEASE/web/$area" >/dev/null 2>&1; then
    continue
  fi
  if [[ -e "$ROOT/web/$area.before-$REVISION" ]]; then
    mv "$ROOT/web/$area" "$ROOT/web/$area.failed-$REVISION"
  else
    mv "$ROOT/web/$area" "$ROOT/web/$area.before-$REVISION"
  fi
  cp -a "$RELEASE/web/$area" "$ROOT/web/$area.next-$REVISION"
  mv "$ROOT/web/$area.next-$REVISION" "$ROOT/web/$area"
  CHANGED_WEB+=("$area")
  chmod -R a+rX "$ROOT/web/$area"
done

trap - ERR
ln -sfn "$RELEASE" "$ROOT/current"
printf '%s %s %s\n' "$(date -u +%FT%TZ)" "$REVISION" "$IMAGE" >> "$ROOT/shared/releases.log"
echo "release ready: $REVISION; external smoke and canary approval remain required"
