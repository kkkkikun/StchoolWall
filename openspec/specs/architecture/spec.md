## Purpose

定义 SchoolWall（鄂应墙）项目的架构决策与设计原则，作为后续技术选型、模块边界划分与系统演进的唯一事实来源。所有影响系统结构的改动应先回到本 spec 比对原则，再决定是否记录为新 ADR。

> 版本：1.0 ｜ 最后更新：2026-07-06 ｜ 维护者：开发团队

## Requirements

### Requirement: 前后端分离与全异步架构

后端 FastAPI 全异步、前端 uni-app 多端编译，二者 MUST 通过版本化 REST API（`/api/v1/*`）通信。

#### Scenario: 新增后端能力

- **WHEN** 后端需要新增业务能力（如评论、通知）
- **THEN** 必须以独立 router 模块形式挂在 `/api/v1/<resource>` 下，遵循 `routers → services → models/schemas` 分层，禁止 router 直接操作 ORM 或跨模块直接 import 其他 service 的内部实现

#### Scenario: 前端调用后端

- **WHEN** 前端需要后端数据
- **THEN** 必须通过 `frontend/src/api/*.ts` 封装的请求层调用，统一经过 `utils/request.ts` 的拦截器（注入 JWT、处理错误码），禁止在页面组件内裸调 uni.request

### Requirement: 鉴权与学籍绑定的安全红线

系统 MUST 保证用户教务系统密码绝不落库，real_name 不在 API 响应中暴露。

#### Scenario: 处理教务系统密码

- **WHEN** 后端执行正方教务系统模拟登录（`utils/zhengfang.py`）
- **THEN** 密码只能存在于请求处理期间的局部内存变量中，验证完成或失败后立即销毁；禁止写入数据库、日志、Redis 或任何持久化介质；`real_name` 抓取后入库但绝不在 API 响应中返回给前端

#### Scenario: 权限升级

- **WHEN** 学籍验证成功
- **THEN** 后端更新 `users.is_verified = True` 并签发包含已认证状态的新 JWT，前端据此解锁发帖与查看他人微信号等高权限操作

### Requirement: 数据层与迁移管理

所有数据库结构变更 MUST 通过 Alembic 迁移脚本管理，禁止手工改库。

#### Scenario: 修改表结构

- **WHEN** 开发者需要新增/修改字段或表
- **THEN** 必须生成并提交 Alembic 迁移脚本（`backend/alembic/versions/`），迁移须可正向与反向执行

#### Scenario: 模型定义

- **WHEN** 定义新数据模型
- **THEN** 模型放在 `backend/app/models/`，对应 Pydantic schema 放在 `backend/app/schemas/`，二者职责分离

### Requirement: 存储与外部依赖适配

文件上传 MUST 通过存储适配器抽象，支持 local / Cloudflare R2 / aliyun 切换。

#### Scenario: 切换存储后端

- **WHEN** 部署环境从本地开发迁移到生产
- **THEN** 仅通过环境变量 `STORAGE_PROVIDER` 及对应凭证切换，业务代码（`services/`、`routers/upload.py`）无需改动；适配器实现在 `utils/storage.py`

### Requirement: 内容审核异步化

发帖审核 MUST 通过后台异步任务处理，不阻塞请求响应。

#### Scenario: 发帖审核流程

- **WHEN** 用户发布带图帖子
- **THEN** 帖子先落库，审核任务进入异步队列（`services/moderation.py` + `utils/moderation.py`），审核期间帖子的可见性由审核状态字段控制；请求接口立即返回，不等待审核完成

### Requirement: 基础设施与部署

开发环境 MUST 使用 Docker Compose 编排 PostgreSQL + Redis；生产 MUST 使用 Nginx 反代 + HTTPS。

#### Scenario: 本地启动依赖

- **WHEN** 开发者拉起本地开发环境
- **THEN** 通过 `docker-compose up -d` 启动 PostgreSQL 15 与 Redis 7，后端从 `.env` 读取连接配置（`config.py` 的 `Settings`）
