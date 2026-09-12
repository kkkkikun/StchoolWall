# Server CI — 服务器端持续集成（全 Docker 化）

## Why

项目已部署到 `http://103.36.221.122:8080/#/`（用户自行部署，HTTP+IP+8080）。当前**没有任何 CI**：428 条 pytest、两端 type-check、三个生产构建（H5/admin/mp-weixin）全靠本地手动跑，回归发现滞后。

用户已确认（2026-09-11 AskUserQuestion）：
- **平台**：服务器端脚本（不用 GitHub Actions）
- **范围**：后端 pytest 全量 + 前端 type-check+构建 + mp-weixin 构建纳入
- **部署联动**：暂不自动部署（CI 只验证打钩，部署保持手动）

## What Changes

- **全 Docker 化 CI**：服务器只需 docker，不装 Python/Node 环境
  - `deploy/ci/docker-compose.ci.yml`：隔离测试栈 `ci-db`（postgres:15，127.0.0.1:5433）+ `ci-redis`（redis:7，127.0.0.1:6380），跑完 `down -v` 销毁——不碰生产容器/生产库/8080 端口
  - `deploy/ci/Dockerfile.backend-ci`：python:3.10-slim + requirements（层缓存，代码改动不重装依赖）
  - `deploy/ci/ci.sh`：编排入口（服务器/本地同一脚本）——起栈 → 等 pg ready → pytest（连 ci-db/ci-redis）→ frontend（type-check + build:h5 + build:mp-weixin）→ admin-frontend（type-check + build）→ 汇总 PASS/FAIL → 产物落 `ci-artifacts/<ts>/`（含自包含 report.html + latest 软链）→ trap 保证失败也清理容器栈
- `deploy/ci/run-ci.sh`：服务器模式入口——`git fetch` 后 checkout `origin/main` → 调 ci.sh
- `deploy/ci/install.sh` + systemd unit/timer：服务器上每小时检测 origin/main，**有新提交才真正跑**（无新提交跳过、不留空报告）
- `deploy/ci/README.md`：服务器手册（clone 需 PAT/deploy key、三条命令、报告/日志位置）
- CI 构建产物（H5 dist 等）只落 artifacts 目录供排查，**不自动部署**

## Impact

- 新增 `deploy/ci/` 目录（5 个文件），零后端/前端代码改动
- 本地 WSL 先完整跑通 ci.sh 作为验收（同一脚本上服务器即用）
- 后续可加 CD（main 绿后 SSH 自动部署）——本次明确不做，留 backlog
