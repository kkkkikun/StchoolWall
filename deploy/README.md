# SchoolWall 网页测试版部署手册

> 自动部署（推送到 main 触发）见 [`GH_ACTIONS.md`](./GH_ACTIONS.md)；本手册是手工部署与服务器初始化流程。

> 目标拓扑：一台公网云服务器 + 域名 + HTTPS。
> 宿主机 nginx 负责 TLS/静态文件/路径分流；db/redis/backend 跑 Docker。

```
用户浏览器
   │ https://your-domain
   ▼
nginx (宿主机, 80/443, certbot)
   ├── /                    → /var/www/schoolwall/h5     （uni-app H5 构建）
   ├── /static/*            → h5/static                  （前端静态资源）
   ├── /static/(avatars|banners|uploads|parties)/ → 后端（用户上传图）
   ├── /admin/              → /var/www/schoolwall/admin  （管理台构建, SPA）
   └── /api/                → 127.0.0.1:8000             （后端容器）
                                            │
                        docker: postgres 15 + redis 7 + backend
```

## 0. 前置条件

- Ubuntu 20.04+/Debian（CentOS 命令自查替换），root 或 sudo 用户
- 域名已解析 A 记录到服务器公网 IP
- 本地开发机能 SSH 到服务器

## 1. 服务器装基础软件

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx rsync
# Docker（官方脚本）
curl -fsSL https://get.docker.com | sudo sh
```

## 2. 本地构建前端产物

```bash
# 小程序 H5（输出 frontend/dist/build/h5/）
cd frontend && npm run build:h5

# 管理后台（子路径 /admin/ 部署，输出 admin-frontend/dist/）
cd ../admin-frontend && npm run build -- --base=/admin/
```

## 3. 同步文件到服务器

```bash
# 假设部署根目录 /opt/schoolwall，站点静态根 /var/www/schoolwall
ssh your-server 'sudo mkdir -p /opt/schoolwall /var/www/schoolwall && sudo chown -R $USER /opt/schoolwall /var/www/schoolwall'
rsync -av --delete backend/ your-server:/opt/schoolwall/backend/
rsync -av --delete deploy/   your-server:/opt/schoolwall/deploy/
rsync -av --delete frontend/dist/build/h5/ your-server:/var/www/schoolwall/h5/
rsync -av --delete admin-frontend/dist/    your-server:/var/www/schoolwall/admin/
```

## 4. 生成生产配置（服务器上）

```bash
cd /opt/schoolwall/deploy
cp env.prod.example .env.prod
vim .env.prod   # 填：JWT_SECRET（openssl rand -hex 32）、DB_PASSWORD、CORS_ORIGINS=https://你的域名
```

## 5. 起后端（自动跑全部数据库迁移）

```bash
cd /opt/schoolwall/deploy
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
docker compose -f docker-compose.prod.yml logs -f backend   # 看到 alembic 迁移跑完 + Uvicorn running
curl http://127.0.0.1:8000/health   # {"status":"ok"}
```

## 6. nginx + HTTPS

```bash
sudo cp nginx.schoolwall.conf /etc/nginx/sites-available/schoolwall
sudo sed -i 's/SERVER_NAME/你的域名/' /etc/nginx/sites-available/schoolwall
sudo ln -sf /etc/nginx/sites-available/schoolwall /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
# 签证书（自动改写 80 块加 301 与 443）
sudo certbot --nginx -d 你的域名
```

## 7. 创建管理台账号（一次性）

```bash
cd /opt/schoolwall/deploy
docker compose -f docker-compose.prod.yml exec backend python -m app.create_admin boss
# 交互输入两次密码（≥8 位）；浏览器开 https://你的域名/admin/ 登录
```

## 8. 验收清单

- [ ] `https://域名/health` → `{"status":"ok"}`，证书小绿锁
- [ ] 我的页「登录 / 注册」注册新账号 → 发帖 → 首页可见（审核通过后）
- [ ] 发一条含敏感词的帖子被自动拦截（管理台「审核记录」可见判定原因）
- [ ] 换头像 → 图片正常显示（`/static/avatars/...` 分流正确）
- [ ] `https://域名/admin/` 管理台登录正常
- [ ] `https://域名/api/v1/auth/dev-login` → 404（安全闸门生效）
- [ ] `https://域名/docs` → 404

## 常见问题

- **改了后端代码**：重跑步骤 3 的 backend rsync + `docker compose ... up -d --build`
- **改了前端**：重跑步骤 2 构建 + 步骤 3 的静态 rsync 即可，不碰后端
- **新增上传 kind**：nginx 的 `/static/` 正则里同步加子目录
- **CORS 报错**：检查 `.env.prod` 的 `CORS_ORIGINS` 是否精确匹配站点域名（协议+域名，不带端口尾斜杠）
- **502**：`docker compose logs backend` 看后端是否起来（常见：JWT_SECRET 没改被闸门拦下）
