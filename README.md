# SchoolWall · 鄂应墙

单校校园社区。FastAPI + PostgreSQL + Redis，uni-app复用Web、微信小程序和Android客户端，独立Vue管理后台。使用固定昵称、头像与主页；学生证人工核验，公开界面隐藏学号与姓名。

当前为生产化改造中的代码版本。**本地检查通过不代表已经可上架或达到容量目标**。实际状态见[交付与发布阻断](docs/production/implementation-status.md)及[验收证据](docs/production/verification.md)。

## 本地开发

需要Python3.10、Node22.12+、PostgreSQL15和Redis7。版本以锁文件和backend/requirements.txt为准。

```sh
cp .env.example backend/.env
docker compose up -d
python3 -m venv venv
venv/bin/pip install -r backend/requirements.txt
cd backend
../venv/bin/python -m alembic upgrade head
../venv/bin/uvicorn app.main:app --reload
```

检查backend/.env中的端口、密码和环境；开发使用ENVIRONMENT=development。学生证默认关闭，开启前须配置独立HMAC密钥和私有存储。无腾讯审核配置时内容进入人工队列。旧教务密码认证接口已停用（410）。

另开终端运行持久任务worker：

```sh
cd backend
../venv/bin/python -m app.worker
```

前端分别进入frontend与admin-frontend执行npm ci。开发命令npm run dev:h5与npm run dev；构建命令分别为build:h5、build:mp-weixin、build:android（后者仅编译App代码，原生签名包仍需DCloud工具链）和管理台build。正式域名、AppID、隐私政策与主体信息必须按实际配置。

## 测试

pytest会清理测试库与Redis，必须显式提供以_test结尾的独立数据库及Redis13/14/15，禁止指向业务库。

```sh
cd backend
ENVIRONMENT=test JWT_EXPIRE_MINUTES=15 \
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/ey_wall_test \
TEST_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@127.0.0.1:5432/ey_wall_test \
REDIS_URL=redis://127.0.0.1:6379/15 TEST_REDIS_URL=redis://127.0.0.1:6379/15 \
../venv/bin/python -m pytest -q
```

CI包括后端集成、迁移、OpenAPI、前端类型与三端代码构建、密钥/依赖/镜像扫描。原生Android包、真机、平台审核、容量与异机恢复必须另附真实证据。

## 安全与运行

- 统一UserUUID，密码/微信登录身份分离；显式配对，不按学号或昵称合并。
- 15分钟access，最长30天refresh轮换，凭证只存哈希；改密、找回、退出、冻结、注销撤销会话。
- Web用HttpOnly刷新cookie与CSRF；Android刷新凭证经Keystore保护；管理台生产强制TOTP。
- 学生证独立私有存储、短时同框码、HMAC、单独同意；结果7天、待审14天删除。
- 公开UGC先隔离与审核，使用media_id验证所有权和用途；任务与业务同事务，独立worker负责重试与接管。
- 审核故障保持待审，管理员队列人工处理；举报、申诉、拉黑、敏感操作审计。
- GET /health/live、/health/ready；/metrics只由内部监控访问。PUBLISHING_ENABLED=false可关闭投稿保留浏览；管理接口也可切换。

管理台初始化运行python -m app.create_admin USERNAME（交互输入密码），再运行python -m app.admin_mfa USERNAME在可信本机交互配置TOTP。ADMIN_MFA_ENCRYPTION_KEY须独立、备份并限制访问。普通用户管理员令牌不授权生产管理API。

## 发布与持续迭代

发布顺序Web→微信小程序→Android。生产使用经CI验证的相同镜像digest和静态产物，迁移单独执行，应用失败回滚。首次迁移清理旧学籍和姓名/学号、演示身份停用，需维护窗口和重新登录；downgrade不会恢复这些个人资料。

- [发布门禁](docs/production/release-gates.md)
- [运行与恢复手册](docs/production/runbook.md)
- [容量验证](docs/production/capacity.md)
- [部署](deploy/README.md)
- [OpenSpec实施清单](openspec/changes/production-multiplatform/tasks.md)

首版不含视频、支付、私信或多校。1万注册/2000日活/500在线是待实测目标；预算500–1500元/月，不能据此预设主机承载能力。
