## Purpose

定义 SchoolWall（鄂应墙）项目的架构决策与设计原则，作为后续技术选型、模块边界划分与系统演进的唯一事实来源。所有影响系统结构的改动应先回到本 spec 比对原则，再决定是否记录为新 ADR。

> 版本：2.0 ｜ 最后更新：2026-10-16 ｜ 维护者：开发团队

## Requirements

### Requirement: 前后端分离与全异步架构

后端 FastAPI 全异步、前端 uni-app 多端编译，二者 MUST 通过版本化 REST API（`/api/v1/*`）通信。

#### Scenario: 新增后端能力

- **WHEN** 后端需要新增业务能力（如评论、通知）
- **THEN** 必须以独立 router 模块形式挂在 `/api/v1/<resource>` 下，遵循 `routers → services → models/schemas` 分层，禁止 router 直接操作 ORM 或跨模块直接 import 其他 service 的内部实现

#### Scenario: 前端调用后端

- **WHEN** 前端需要后端数据
- **THEN** 必须通过 `frontend/src/api/*.ts` 封装的请求层调用，统一经过 `utils/request.ts` 的拦截器（注入 JWT、处理错误码），禁止在页面组件内裸调 uni.request

### Requirement: 统一身份、短会话与私有学生证核验

系统 MUST 分离用户、登录身份、设备会话与学籍认证；生产停用教务密码认证。学生原始姓名和学号 MUST NOT 持久化，公开资料仅使用固定昵称。

#### Scenario: 跨端登录与绑定

- **WHEN** 用户在Web、微信小程序或Android登录或绑定已有账号
- **THEN** 按登录身份明确关联同一用户UUID；禁止按昵称、学号自动合并；绑定需短时单次配对与新近认证，已有内容身份进入人工流程

#### Scenario: 会话撤销

- **WHEN** access过期、refresh轮换重放，或用户改密、找回、退出、冻结、注销
- **THEN** 15分钟access与最长30天refresh受服务端会话约束，凭证只存哈希，相关会话立即撤销；生产管理台仅允许独立账号与MFA

#### Scenario: 学生证认证与删除

- **WHEN** 学生提交学生证照片及同框随机码
- **THEN** 独立私有存储与授权人工核验，保存学校/独立HMAC指纹/有效期，结果7天、待审14天删除并支持恢复后的继续清理；教务密码接口返回410

### Requirement: 数据层与迁移管理

所有数据库结构变更 MUST 通过 Alembic 迁移脚本管理，禁止手工改库。

#### Scenario: 修改表结构

- **WHEN** 开发者需要新增/修改字段或表
- **THEN** 必须生成并提交 Alembic 迁移脚本（`backend/alembic/versions/`），迁移须可正向与反向执行

#### Scenario: 模型定义

- **WHEN** 定义新数据模型
- **THEN** 模型放在 `backend/app/models/`，对应 Pydantic schema 放在 `backend/app/schemas/`，二者职责分离

### Requirement: 存储与外部依赖适配

媒体 MUST 通过私有存储适配器隔离处理；开发支持local，生产采用独立COS存储。学生证使用独立私有桶，不进入公共内容审核、CDN或普通媒体备份。

#### Scenario: 切换存储后端

- **WHEN** 部署环境从本地开发迁移到生产
- **THEN** 通过环境变量 `STORAGE_PROVIDER` 及对应凭证切换，业务代码（`services/`、`routers/upload.py`）无需改动；适配器实现在 `utils/storage.py`

### Requirement: 内容审核异步化

公开UGC审核 MUST 使用与业务同事务提交的PostgreSQL任务，由独立worker处理。机器故障或配置缺失保持待审，支持人工队列。

#### Scenario: 发帖审核流程

- **WHEN** 用户发布带图帖子
- **THEN** 帖子先落库，审核任务进入持久任务表（`services/moderation.py` + `utils/moderation.py`），审核期间帖子的可见性由审核状态字段控制；请求接口立即返回，不等待审核完成

### Requirement: 基础设施与部署

开发环境 MUST 使用 Docker Compose 编排 PostgreSQL + Redis；生产 MUST 使用 Nginx 反代 + HTTPS。

#### Scenario: 本地启动依赖

- **WHEN** 开发者拉起本地开发环境
- **THEN** 通过 `docker-compose up -d` 启动 PostgreSQL 15 与 Redis 7，后端从 `.env` 读取连接配置（`config.py` 的 `Settings`）

### Requirement: 证据驱动的生产发布

生产 MUST 使用同一CI验证产物、独立单次迁移、健康检查、监控、备份与应用回滚；缺少门禁证据不得发布。

#### Scenario: 首次真实开放

- **WHEN** 准备Web、小程序或Android发布
- **THEN** 必须取得实际主体资质、备案/平台审核、安全、容量与恢复证据；目标99.5%可用性、RPO≤1小时、RTO≤4小时均以演练验收，不能视为代码保证

#### Scenario: 迭代交付

- **WHEN** 生产化阶段完成代码或验证
- **THEN** 更新变更任务、迁移说明、测试证据与运行手册，未执行的真机、故障或平台门禁保持未完成