# SchoolWall CI — 服务器端持续集成手册

全 Docker 化测试管线：服务器**只需要 docker**（不装 Python/Node）。与生产部署完全解耦——不碰生产容器、生产库、8080 端口。

```
stack_up → backend_image → backend_pytest → frontend_build → admin_build → report.html
 (隔离PG/Redis)  (依赖层缓存)   (428 tests)    (type-check+H5+MP)  (type-check+build)
```

测试栈跑在 `127.0.0.1:5433/6380`（仅本机），每轮结束 `down -v` 销毁。

---

## 1. 前提

| 项 | 要求 |
|---|---|
| docker + compose v2 | `docker compose version` 有输出 |
| 网络 | 能访问 docker.io（拉基础镜像）与 npm registry |
| 磁盘 | ≥2GB 空余（镜像 + npm 缓存卷 + artifacts） |

## 2. 拉代码（私有仓凭证，二选一）

```bash
# 方式 A：HTTPS + Personal Access Token（GitHub → Settings → Developer settings → PAT，勾 repo 读权限）
git clone https://<你的用户名>:<PAT>@github.com/kkkkikun/StchoolWall.git ~/schoolwall
# 方式 B：SSH deploy key（只读密钥，推荐）
ssh-keygen -t ed25519 -f ~/.ssh/schoolwall_ci -N ''
cat ~/.ssh/schoolwall_ci.pub   # 填到 GitHub 仓库 Settings → Deploy keys
#   ~/.ssh/config 加：
#   Host github-schoolwall
#     HostName github.com
#     IdentityFile ~/.ssh/schoolwall_ci
git clone git@github-schoolwall:kkkkikun/StchoolWall.git ~/schoolwall
```

> clone 的用户就是 service 运行用户（install.sh 自动检测），凭证须对该用户可用。

## 3. 一键安装（timer 每小时自动跑）

```bash
cd ~/schoolwall
./deploy/ci/install.sh          # 装 systemd service + timer 并启用
./deploy/ci/install.sh --run    # 同上，并立即手动触发一轮（跟随日志）
```

timer 逻辑：每小时 fetch 一次，**origin/main 有新提交才真正跑**，无新提交秒退（近乎零开销）。

## 4. 日常使用

```bash
# 看下轮触发时间
systemctl list-timers schoolwall-ci.timer

# 手动跑一轮（不等 timer）
sudo systemctl start schoolwall-ci.service

# 看运行日志
journalctl -u schoolwall-ci.service -f

# 只跑某几个阶段（调试用，需在仓库目录）
./deploy/ci/ci.sh backend_pytest          # 自动前置起栈
./deploy/ci/ci.sh frontend_build
```

## 5. 看报告

每轮产物落 `仓库/ci-artifacts/<时间戳>/`，`latest` 软链指向最新：

```
ci-artifacts/latest/
├── report.html      # 各阶段 PASS/FAIL + 耗时
├── *.log            # 每阶段完整日志
└── mp-weixin/       # 小程序构建包（可拷去微信开发者工具）
```

浏览器查看（只绑本机，SSH 用户可 `ssh -L 8899:127.0.0.1:8899 服务器` 后访问 localhost:8899）：

```bash
cd ~/schoolwall/ci-artifacts && python3 -m http.server 8899 --bind 127.0.0.1
```

## 6. 故障排查

| 症状 | 处理 |
|------|------|
| backend_image 卡在拉 python 镜像 | 服务器连 docker.io 慢/被断：重跑一次；或 `docker pull python:3.11-slim` 手动预热 |
| run-ci 报 git 权限错 | service 用户的 git 凭证失效（PAT 过期/密钥被删）——重新按 §2 配 |
| 磁盘涨 | `docker system prune -f`（悬空层）+ 删旧 `ci-artifacts/` 保留最近若干份 |
| timer 没跑 | `systemctl status schoolwall-ci.timer`、`journalctl -u schoolwall-ci.service -n 50` |

## 7. 本地（WSL）首次运行提示

本地 Docker Hub 直连可能被断（`connection reset`）。一次性预热基础镜像即可：

```bash
docker pull docker.m.daocloud.io/library/python:3.11-slim && docker tag docker.m.daocloud.io/library/python:3.11-slim python:3.11-slim
docker pull docker.m.daocloud.io/library/node:20-alpine    && docker tag docker.m.daocloud.io/library/node:20-alpine node:20-alpine
```

服务器（境外）通常直连正常，无需此步。

## 8. 后续演进（backlog）

- main 绿后自动部署（CD）：新增 deploy 阶段 SSH 到生产目录 `git pull && docker compose up -d --build`
- 失败通知（Server 酱 / 邮件 / webhook）
- Playwright E2E 进管线（需起完整服务栈，较重）
