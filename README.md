# SchoolWall · 鄂应墙

> 校园匿名墙 / 信息撮合平台 —— 微信小程序（uni-app + Vue3）+ FastAPI 全异步后端。

核心链路：**微信静默授权发游客 JWT → 正方教务系统验证学籍后升级为已认证 JWT**。已认证用户可发帖、评论、点赞、收藏、组局。

> 🔒 安全红线：教务系统密码**绝不落库**；`real_name` 仅作核验、绝不在前端暴露；用户间联系走 `wechat_id` 站外引流（**不做站内 IM**）。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10 · FastAPI · Uvicorn（全异步） |
| ORM/DB | SQLAlchemy 2.0 async · asyncpg · Alembic · **PostgreSQL 15** |
| 缓存/队列 | Redis 7（Token 校验 / 限流 / 异步审核） |
| 认证 | python-jose JWT · 微信 `wx.login` · 正方教务系统爬虫（rsa + bs4 + httpx） |
| 存储 | boto3 适配器（local / Cloudflare R2 / aliyun） |
| 前端 | uni-app（Vue 3 + Vite 5 + TypeScript）· 多端编译，首选微信小程序 |
| 基础设施 | Docker Compose（PG + Redis）；生产 Nginx + HTTPS |
| 测试 | pytest + pytest-asyncio（独立测试库 + NullPool + 每测试 TRUNCATE） |

---

## 功能模块

- ✅ **鉴权**：微信登录 + 正方学籍认证（双 JWT）
- ✅ **帖子**：CRUD、游标分页信息流、广告置顶、举报、状态流转
- ✅ **互动**：评论 / 点赞 / 收藏 / 浏览足迹 + 帖子计数 + 个人统计
- ✅ **发现**：十大热帖（加权排序）+ 全文搜索
- ✅ **消息通知**：评论/赞通知、未读汇总、全部已读（无私信）
- ✅ **上传**：图片/视频，异步内容审核
- ✅ **管理后台**：举报 / 用户管理
- ⏳ **组局·攒局**：组局/拼单 + 报名进度（开发中）

---

## 项目结构

```
SchoolWall/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── main.py          # 入口、路由注册
│   │   ├── config.py        # Settings（环境变量）
│   │   ├── models/          # user / post / tag / report / interaction / notification
│   │   ├── routers/         # auth / user / posts / interaction / notification / upload / tags / admin
│   │   ├── services/        # 业务逻辑（薄 router → service）
│   │   ├── schemas/         # Pydantic
│   │   └── utils/           # security / redis / rate_limit / storage / zhengfang / moderation
│   ├── alembic/versions/    # 数据库迁移
│   └── tests/               # pytest（conftest + 独立测试库）
├── frontend/                # uni-app 前端
│   └── src/
│       ├── pages/           # index / group / publish / message / mine / post-detail / search / verify / admin ...
│       ├── components/      # feed-card / tab-bar / ui-icon
│       ├── api/             # 请求封装（按模块）
│       └── utils/           # request / storage / mock
├── openspec/                # 需求规范（唯一事实来源）—— 见下
├── ref/                     # 前端设计参考稿
├── docker-compose.yml       # PostgreSQL + Redis
└── SchoolWall.md            # 原始 MVP 技术实现文档
```

---

## 快速开始

### 1. 起依赖（PostgreSQL + Redis）

```bash
docker compose up -d
```

### 2. 后端

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # 按需填写 JWT_SECRET / 微信 / 正方 等
alembic upgrade head           # 建表

# 测试（需先建测试库）
docker exec schoolwall-db-1 psql -U eywall -d postgres -c "CREATE DATABASE ey_wall_test;"
pytest                         # 150 passed

# 运行
uvicorn app.main:app --reload --port 8000
# API 文档：http://localhost:8000/docs
```

### 3. 前端（H5 预览）

```bash
cd frontend
npm install
npm run dev:h5                 # http://localhost:5173 （/api 自动代理到 :8000）
# 微信小程序：npm run dev:mp-weixin，用微信开发者工具导入 dist/dev/mp-weixin
```

> H5 预览无微信环境，提供 **dev-login**（仅 `ENVIRONMENT=development`）：我的页「一键登录（演示）」可直接以演示学生身份体验。

---

## 开发规范（OpenSpec）

本项目用 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 管理需求与变更，**规范是唯一事实来源**：

- `openspec/specs/` —— architecture / rules / learned / references / optimization
- `openspec/changes/` —— 进行中的变更提案
- 入口索引：`CLAUDE.md`；状态快照：`.claude/docs/SNAPSHOT.md`

常用命令：`/opsx:propose`（提案）· `/opsx:apply`（实施）· `/opsx:archive`（归档）· `openspec validate --specs`（校验）。

---

## License

私有项目。
