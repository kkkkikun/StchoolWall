## Purpose

记录 SchoolWall 的依赖版本与外部参考资源，确保构建可重现、依赖可追溯、外部文档可获取。新增或升级依赖时必须同步更新本文件。

> 版本：1.0 ｜ 最后更新：2026-07-06
> 依赖来源：`backend/requirements.txt`、`frontend/package.json`、`admin-frontend/package.json`、`.env.example`、`docker-compose.yml`

## Requirements

### Requirement: 后端依赖记录

Python 后端关键依赖 MUST 可追溯版本与用途。

#### Scenario: 查询后端依赖

- **WHEN** 需要确认某个后端库的版本或用途
- **THEN** 查阅下表（来自 `backend/requirements.txt`）：

| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | 0.143.2 | Web 框架 |
| starlette | 1.7.0 | ASGI 框架（显式锁定版本） |
| uvicorn[standard] | 0.34.0 | ASGI 服务器 |
| sqlalchemy[asyncio] | 2.0.36 | ORM（异步） |
| asyncpg | 0.30.0 | PostgreSQL 异步驱动 |
| alembic | 1.14.0 | 数据库迁移 |
| redis[hiredis] | 5.2.1 | 缓存/队列 |
| pyjwt | 2.15.1 | JWT 签发与校验 |
| pydantic-settings | 2.7.1 | 配置管理 |
| httpx | 0.28.1 | HTTP 客户端（爬虫） |
| rsa | 4.9 | 正方登录 RSA 加密 |
| beautifulsoup4 | 4.12.3 | 正方登录 HTML 解析 |
| boto3 | 1.36.2 | Cloudflare R2 / S3 兼容存储 |
| python-multipart | 0.0.32 | 文件上传解析 |
| pytest | 9.1.1 | 测试框架 |
| pytest-asyncio | 1.4.0 | 异步测试支持 |
| bcrypt | 4.2.1 | 管理员与网页登录口令散列 |
| Pillow | 13.0.0 | 用户上传图片解码、去 EXIF 与证件材料处理（13.0.0 起要求 Python ≥ 3.11） |
| cryptography | 50.0.2 | 证件材料与密钥加密 |
| tencentcloud-sdk-python | 3.1.188 | 腾讯云内容审核 |
| cos-python-sdk-v5 | 1.9.44 | 腾讯云 COS 私有存储 |
| prometheus-client | 0.23.1 | HTTP 指标暴露 |

- **运行时**：Python 3.11（开发机实测 3.11.15）

### Requirement: 前端依赖记录

uni-app 前端关键依赖 MUST 可追溯。

#### Scenario: 查询前端依赖

- **WHEN** 需要确认前端框架或构建工具版本
- **THEN** 查阅下表：

学生端（`frontend/package.json`）：

| 依赖 | 版本 | 用途 |
|------|------|------|
| @dcloudio/uni-app / uni-app-plus / uni-components / uni-h5 / uni-mp-weixin | 3.0.0-5020620260917001 | uni-app 运行时与多端编译（版本统一锁定） |
| vue | ^3.4.21 | 视图框架 |
| typescript | ~5.9.3 | 类型系统（dev） |
| vite | 7.3.7 | 构建工具（dev） |
| vue-tsc | ^3.3.13 | 类型检查（dev，`npm run type-check`） |
| openapi-typescript | ^7.13.0 | 由后端契约生成前端类型（dev，`npm run generate:api`） |

管理台（`admin-frontend/package.json`）：

| 依赖 | 版本 | 用途 |
|------|------|------|
| vue | ^3.5.13 | 视图框架 |
| element-plus | ^2.9.1 | UI 组件库（按需引入） |
| echarts | 6.1.0 | 看板图表（按需注册） |
| pinia | ^2.3.0 | 状态管理 |
| vue-router | ^4.5.0 | 路由 |
| axios | ^1.7.9 | HTTP 客户端 |
| vite | ^6.0.5 | 构建工具（dev） |
| typescript | ~5.7.2 | 类型系统（dev） |
| vue-tsc | ~3.1.8 | 类型检查（dev；锁 3.1.x 是因为 3.2/3.3 对本仓库模板误报，见 `openspec/specs/learned/spec.md`） |

- **目标平台**：首选微信小程序（`dev:mp-weixin`），支持 H5/多端；管理台为独立 Web 应用（`build:admin`，部署前缀 `/admin/`）

### Requirement: 基础设施与外部服务

外部服务与基础设施版本 MUST 记录，便于环境对齐。

#### Scenario: 拉起本地依赖

- **WHEN** 需要对齐本地与生产的基础设施版本
- **THEN** 查阅下表：

| 服务 | 版本/配置 | 说明 |
|------|----------|------|
| PostgreSQL | 15-alpine | docker-compose `db`，库 `ey_wall`（测试库 `ey_wall_test`） |
| Redis | 7-alpine | docker-compose `redis`，db 0 |
| 正方教务系统 | 见 `ZHENGFANG_BASE_URL` | 学籍实名数据源 |
| 微信开放平台 | `WECHAT_APP_ID/SECRET` | 小程序登录、openid 换取 |

### Requirement: 外部文档与参考资源

项目参考的重要外部文档 MUST 记录链接与摘要。

#### Scenario: 查阅设计依据

- **WHEN** 需要回溯项目原始需求与设计决策
- **THEN** 查阅 `SchoolWall.md`（仓库根，约 28KB）—— 鄂应墙 MVP 技术实现文档，含架构选型、鉴权链路、数据库表结构定义

#### Scenario: 查阅 OpenSpec 用法

- **WHEN** 需要了解 OpenSpec CLI 命令
- **THEN** 参考 GitHub：https://github.com/Fission-AI/OpenSpec

### Requirement: 项目分析文档索引

openspec-explorer 生成的深度分析文档 MUST 在此注册索引。

#### Scenario: 生成分析文档

- **WHEN** 通过 `/opsx:explore` 或 openspec-explorer 生成 `.claude/analysis/` 文档
- **THEN** 在本 Requirement 下追加索引条目：主题、路径、内容概要（当前暂无）
