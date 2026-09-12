# Server CI — 任务清单

## 批1：CI 脚本套件（本地开发+验证）

- [x] T1 `deploy/ci/docker-compose.ci.yml`（ci-db:5433 / ci-redis:6380，仅绑 127.0.0.1，跑完 down -v）
- [x] T2 `deploy/ci/Dockerfile.backend-ci`（python:3.10-slim + requirements 层缓存）
- [x] T3 `deploy/ci/ci.sh` 编排：起栈→pg_isready→后端 pytest→frontend（type-check+build:h5+build:mp-weixin）→admin（type-check+build）→汇总+report.html+latest 软链→trap 清理
- [x] T4 本地 WSL 完整跑通 ci.sh（Gate 5 证据：428 passed + 三构建绿 + 容器栈清理干净）

## 批2：服务器接入件

- [x] T5 `deploy/ci/run-ci.sh`（git fetch + checkout origin/main + 调 ci.sh，退出码透传）
- [x] T6 `deploy/ci/install.sh` + `schoolwall-ci.service`/`schoolwall-ci.timer`（hourly，无新提交则跳过）
- [x] T7 `deploy/ci/README.md` 手册（clone 凭证、安装、报告/日志查看、故障排查）

## 批3：服务器执行（用户配合）

- [ ] T8 用户在 103.36.221.122 执行 install.sh（或按手册分步），确认 timer 跑过一轮全绿
