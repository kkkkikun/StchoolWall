## Purpose

记录 SchoolWall 的依赖版本与外部参考资源，确保构建可重现、依赖可追溯、外部文档可获取。新增或升级依赖时必须同步更新本文件。

> 版本：1.0 ｜ 最后更新：2026-07-06
> 依赖来源：`backend/requirements.txt`、`frontend/package.json`、`.env.example`、`docker-compose.yml`

## Requirements

### Requirement: 后端依赖记录

Python 后端关键依赖 MUST 可追溯版本与用途。

#### Scenario: 查询后端依赖

- **WHEN** 需要确认某个后端库的版本或用途
- **THEN** 查阅下表（来自 `backend/requirements.txt`）：

| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | 0.115.6 | Web 框架 |
| uvicorn[standard] | 0.34.0 | ASGI 服务器 |
| sqlalchemy[asyncio] | 2.0.36 | ORM（异步） |
| asyncpg | 0.30.0 | PostgreSQL 异步驱动 |
| alembic | 1.14.0 | 数据库迁移 |
| redis[hiredis] | 5.2.1 | 缓存/队列 |
| python-jose[cryptography] | 3.3.0 | JWT |
| pydantic-settings | 2.7.1 | 配置管理 |
| httpx | 0.28.1 | HTTP 客户端（爬虫） |
| rsa | 4.9 | 正方登录 RSA 加密 |
| beautifulsoup4 | 4.12.3 | 正方登录 HTML 解析 |
| boto3 | 1.36.2 | Cloudflare R2 / S3 兼容存储 |
| python-multipart | 0.0.20 | 文件上传解析 |
| Pillow | 13.0.0 | 用户上传图片解码、去 EXIF 与证件材料处理（13.0.0 起要求 Python ≥ 3.11） |
| pytest | 8.3.4 | 测试框架 |
| pytest-asyncio | 0.24.0 | 异步测试支持 |

- **运行时**：Python 3.11（开发机实测 3.11.15）

### Requirement: 前端依赖记录

uni-app 前端关键依赖 MUST 可追溯。

#### Scenario: 查询前端依赖

- **WHEN** 需要确认前端框架或构建工具版本
- **THEN** 查阅下表（来自 `frontend/package.json`）：

| 依赖 | 版本 | 用途 |
|------|------|------|
| @dcloudio/uni-app | 3.0.0-4080420251103001 | uni-app 核心（多端编译） |
| vue | ^3.4.21 | 视图框架 |
| vue-i18n | ^9.1.9 | 国际化 |
| typescript | ^4.9.4 | 类型系统（dev） |
| vite | 5.2.8 | 构建工具（dev） |
| vue-tsc | ^1.0.24 | 类型检查（dev，`npm run type-check`） |

- **目标平台**：首选微信小程序（`dev:mp-weixin`），支持 H5/多端

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
