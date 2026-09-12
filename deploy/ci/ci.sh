#!/usr/bin/env bash
# SchoolWall CI — 全 Docker 化测试管线（服务器与本地 WSL 同一脚本）。
#
# 阶段：stack-up → backend-image → backend-pytest → frontend-build → admin-build
# 产出：ci-artifacts/<时间戳>/ 各阶段日志 + report.html + mp-weixin 构建包
# 清理：trap EXIT 保证任何退出路径都销毁测试栈（down -v）
#
# 用法：./deploy/ci/ci.sh [阶段...]   # 缺省全跑；可传子集如 backend-pytest
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/deploy/ci/docker-compose.ci.yml"
NET_NAME="schoolwall-ci-net"
STAMP="$(date +%Y%m%d-%H%M%S)"
ART="$ROOT/ci-artifacts/$STAMP"
NPM_CACHE_VOL="schoolwall-npm-cache"

# 与本地跑绿的 backend/.env 等价的测试环境（安全闸门只在 production 触发；
# JWT_SECRET 为 CI 一次性占位密钥，不签发任何生产有效 token；
# ZHENGFANG_BASE_URL 非空即可——verify 测试均 mock 爬虫或在触网前返回，
# 留空会被 /auth/verify 的配置门禁拦成 400，见 routers/auth.py）
export BACKEND_ENV=(
  -e "DATABASE_URL=postgresql+asyncpg://postgres:postgres@ci-db:5432/ey_wall"
  -e "REDIS_URL=redis://ci-redis:6379/0"
  -e "ENVIRONMENT=development"
  -e "DEV_LOGIN_ENABLED=true"
  -e "JWT_SECRET=ci-only-placeholder-secret-0123456789abcdef"
  -e "ZHENGFANG_BASE_URL=http://zhengfang.invalid"
)

# node 构建容器公共参数：挂源码 + 匿名卷遮蔽 node_modules（隔离宿主 glibc 依赖，
# 也避免容器内 npm ci 重装污染宿主），npm 下载缓存走命名卷加速后续运行
NODE_RUN=(
  docker run --rm --network host
  -v "schoolwall-npm-cache:/root/.npm"
)

log() { printf '\033[36m[ci]\033[0m %s\n' "$*"; }

cleanup() {
  log "清理测试栈…"
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

# ---------------------------------------------------------------- 阶段框架
declare -a STAGE_NAME=() STAGE_STATUS=() STAGE_TIME=()

run_stage() { # run_stage <名称> <命令> <args...>；日志 tee 到产物目录
  local name="$1" t0=$SECONDS
  shift
  log "▶ $name"
  if "$@" > >(tee "$ART/$name.log") 2>&1; then
    STAGE_NAME+=("$name"); STAGE_STATUS+=("PASS"); STAGE_TIME+=("$((SECONDS - t0))s")
    log "✓ $name 通过 ($((SECONDS - t0))s)"
    return 0
  else
    STAGE_NAME+=("$name"); STAGE_STATUS+=("FAIL"); STAGE_TIME+=("$((SECONDS - t0))s")
    log "✗ $name 失败（详见 $ART/$name.log）"
    FAILED=1
    return 1
  fi
}

# ---------------------------------------------------------------- 各阶段
stage_stack_up() {
  docker compose -f "$COMPOSE_FILE" up -d
  # 显式等健康（兼容旧版 compose 无 --wait）：pg_isready + redis ping
  local i ok
  for i in $(seq 1 30); do
    ok=0
    docker compose -f "$COMPOSE_FILE" exec -T ci-db pg_isready -U postgres >/dev/null 2>&1 && \
      docker compose -f "$COMPOSE_FILE" exec -T ci-redis redis-cli ping >/dev/null 2>&1 && ok=1
    [ "$ok" = 1 ] && return 0
    sleep 2
  done
  log "测试栈 60s 内未就绪"; return 1
}

stage_backend_image() {
  docker build -t schoolwall-ci-backend:latest -f "$ROOT/deploy/ci/Dockerfile.backend-ci" "$ROOT/backend"
}

stage_backend_pytest() {
  docker run --rm --network "$NET_NAME" \
    "${BACKEND_ENV[@]}" \
    schoolwall-ci-backend:latest
}

stage_frontend_build() {
  "${NODE_RUN[@]}" \
    -v "$ROOT/frontend":/src -w /src \
    -v /src/node_modules \
    node:20-alpine sh -ec \
    'npm ci --no-audit --no-fund \
     && npm run type-check \
     && npm run build:h5 \
     && npm run build:mp-weixin'
  # 产物留档：mp-weixin 包可直接拷去微信开发者工具
  mkdir -p "$ART/mp-weixin"
  cp -r "$ROOT/frontend/dist/build/mp-weixin/." "$ART/mp-weixin/"
}

stage_admin_build() {
  "${NODE_RUN[@]}" \
    -v "$ROOT/admin-frontend":/src -w /src \
    -v /src/node_modules \
    node:20-alpine sh -ec \
    'npm ci --no-audit --no-fund \
     && npm run type-check \
     && npm run build'
}

# ---------------------------------------------------------------- 汇总
write_report() {
  local commit when row rows=""
  commit="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  when="$(date '+%F %T')"
  for i in "${!STAGE_NAME[@]}"; do
    rows+="    <tr><td>${STAGE_NAME[$i]}</td><td class=\"${STAGE_STATUS[$i]}\">${STAGE_STATUS[$i]}</td><td>${STAGE_TIME[$i]}</td></tr>"$'\n'
  done
  cat > "$ART/report.html" <<HTML
<!doctype html>
<meta charset="utf-8">
<title>SchoolWall CI ${STAMP}</title>
<style>
  body{font:14px/1.6 system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;color:#333}
  h1{font-size:20px}
  table{border-collapse:collapse;width:100%}
  th,td{border:1px solid #ddd;padding:8px 12px;text-align:left}
  th{background:#fafafa}
  .PASS{color:#1677ff;font-weight:600}
  .FAIL{color:#d4380d;font-weight:600}
  li{margin:4px 0}
</style>
<h1>SchoolWall CI 报告</h1>
<p>commit <code>${commit}</code> · ${when}</p>
<table>
  <tr><th>阶段</th><th>状态</th><th>耗时</th></tr>
$(printf '%s' "$rows")
</table>
<p>各阶段日志与 mp-weixin 构建包在本目录；历史报告见 <code>ci-artifacts/</code>。</p>
HTML
  ln -sfn "$STAMP" "$ROOT/ci-artifacts/latest"
}

# ---------------------------------------------------------------- 主流程
FAILED=0
mkdir -p "$ART"

ALL_STAGES=(stack_up backend_image backend_pytest frontend_build admin_build)
# 阶段名 → 函数名（git 风格中划线转下划线）
fn_of() { echo "stage_${1//-/_}"; }

if [ "$#" -gt 0 ]; then REQUESTED=("$@"); else REQUESTED=("${ALL_STAGES[@]}"); fi

# backend_pytest 依赖测试栈：未显式请求 stack_up 时自动前置（幂等），便于单阶段调试
if printf '%s\n' "${REQUESTED[@]}" | grep -qx backend_pytest \
   && ! printf '%s\n' "${REQUESTED[@]}" | grep -qx stack_up; then
  REQUESTED=(stack_up "${REQUESTED[@]}")
fi

for s in "${REQUESTED[@]}"; do
  if ! declare -F "$(fn_of "$s")" >/dev/null; then
    log "未知阶段：$s（可选：${ALL_STAGES[*]}）"; exit 2
  fi
done

# 单阶段失败不中断后续检查（一次看到全部问题）：run_stage 只记录状态并置 FAILED
for s in "${REQUESTED[@]}"; do
  run_stage "$s" "$(fn_of "$s")" || true
done

write_report

echo
log "========== 汇总 =========="
for i in "${!STAGE_NAME[@]}"; do
  printf '  %-16s %-4s %s\n' "${STAGE_NAME[$i]}" "${STAGE_STATUS[$i]}" "${STAGE_TIME[$i]}"
done
log "产物目录：$ART（report.html / *.log / mp-weixin）"

exit "$FAILED"
