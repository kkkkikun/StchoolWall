# GitHub Actions 自动部署手册（方案一：SSH 远程执行）

> 推送到 `main` → GitHub Actions 通过 SSH 登录服务器 → `git pull` → Docker 构建前端/后端 → 健康检查。
> 服务器只需 docker + git + rsync，**不需要** Node/Python（前端构建跑在容器里）。
> 前置的服务器初始化（nginx/HTTPS/.env.prod/管理台账号）仍按 [`README.md`](./README.md) 执行，本手册只补「自动化」部分。

## 1. 服务器：生成部署专用密钥（仅用于 Actions 登录服务器）

```bash
# 在服务器上执行（不要用你的个人密钥）
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/schoolwall_deploy -N ''
cat ~/.ssh/schoolwall_deploy.pub >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

> 私钥 `~/.ssh/schoolwall_deploy` 的**全部内容**下一步填到 GitHub Secrets；公钥已进 `authorized_keys`。
> 可用本机验证：`ssh -i schoolwall_deploy user@你的服务器 echo ok`。

## 2. 服务器：clone 私有仓库（给 `git pull` 用，二选一）

仓库是私有的，服务器必须有只读凭证才能 pull。

- **方式 B（推荐，只读 deploy key）**：见 [`ci/README.md`](./ci/README.md) 第 2 节——
  服务器生成独立密钥 → 公钥填 GitHub 仓库 *Settings → Deploy keys*（不勾 write）→ clone 到 `/opt/schoolwall`。
- **方式 A**：HTTPS + PAT：`git clone https://<用户名>:<PAT>@github.com/kkkkikun/StchoolWall.git /opt/schoolwall`

```bash
# 目录归属部署用户（Actions 用该用户登录）
sudo mkdir -p /opt/schoolwall /var/www/schoolwall
sudo chown -R $USER /opt/schoolwall /var/www/schoolwall
git clone <上述任一地址> /opt/schoolwall
```

## 3. GitHub 仓库配置 Secrets

*Settings → Secrets and variables → Actions → New repository secret*：

| Secret | 必需 | 值 |
|---|---|---|
| `SERVER_HOST` | ✅ | 服务器 IP 或域名 |
| `SERVER_USERNAME` | ✅ | 登录用户名（`/opt/schoolwall` 的属主） |
| `SERVER_SSH_KEY` | ✅ | `~/.ssh/schoolwall_deploy` 私钥**全部内容**（含首尾 BEGIN/END 行） |
| `DEPLOY_PATH` | 可选 | 默认 `/opt/schoolwall`，不一致才配 |
| `WEB_ROOT` | 可选 | 默认 `/var/www/schoolwall`，不一致才配 |

## 4. 触发与验证

- **自动**：推送到 `main` 即触发（见 `.github/workflows/deploy.yml`）
- **手动**：*Actions → Deploy to Server → Run workflow*
- 看结果：仓库 *Actions* 页签，job 日志末尾出现 `deploy ok: backend healthy` 即成功
- 同一时间只有一个部署在跑（`concurrency`），不会互相踩

## 5. 部署内容

| 步骤 | 动作 |
|---|---|
| 1 | `git pull --ff-only origin main` |
| 2 | docker 跑 `node:20-alpine` 构建 H5 + 管理台（`npm ci`，缓存挂 `.npm-cache/`） |
| 3 | `rsync --delete` 到 `/var/www/schoolwall/{h5,admin}` |
| 4 | `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build`（自动 Alembic 迁移） |
| 5 | 轮询 `http://127.0.0.1:8000/health`，60s 不 healthy 则 job 失败 |

## 6. 常见问题

- **`Permission denied (publickey)`**：`SERVER_SSH_KEY` 没粘全（要含 `-----BEGIN OPENSSH PRIVATE KEY-----` 整段）；确认公钥进了服务器 `authorized_keys`
- **`fatal: could not read Username`**：服务器 clone 凭证没配好（第 2 步），pull 需要只读 deploy key 或 PAT
- **`.env.prod` not found**：按 [`README.md`](./README.md) 第 4 步先在服务器生成
- **改动了 nginx 配置**：workflow 不碰 nginx，需手动按 README 第 6 步重载
- **回滚**：`git revert` 后推送，或在服务器上手动操作
