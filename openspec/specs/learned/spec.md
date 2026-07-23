## Purpose

记录 SchoolWall 开发过程中学到的知识——API 路径、踩坑档案、技巧模式、文件速查——避免重复探索，加速问题解决。日常由 assistant 按需追加，遵循"学到即记、记即精准"。

> 版本：1.0 ｜ 最后更新：2026-07-06
> 初始种子条目来自项目初始化时的已核实事实；后续开发中持续追加。

## Requirements

### Requirement: API 路径速查

后端路由前缀与用途 MUST 可被快速查阅，方便前后端联调。

#### Scenario: 查询路由归属

- **WHEN** 需要定位某个资源的后端入口
- **THEN** 查阅下表（注册于 `backend/app/main.py`）：

| 前缀 | Router 文件 | 用途 |
|------|------------|------|
| `/api/v1/auth` | `routers/auth.py` | 微信登录、学籍绑定、JWT 签发 |
| `/api/v1/user` | `routers/user.py` | 用户资料、微信号维护 |
| `/api/v1/posts` | `routers/posts.py` | 帖子 CRUD、隐私隔离 |
| `/api/v1/upload` | `routers/upload.py` | 图片上传（local/R2/aliyun） |
| `/api/v1/tags` | `routers/tags.py` | 标签管理 |
| `/api/v1/admin` | `routers/admin.py` | 管理后台、审核 |
| `/health` | `main.py` | 健康检查 |

### Requirement: 踩坑档案

耗费较长时间排查的问题 MUST 记录症状/根因/解法/预防。

#### Scenario: asyncpg 跨事件循环报错

- **WHEN** 测试中出现 asyncpg "another operation in progress" 或事件循环相关错误
- **THEN** 根因：asyncpg 连接绑定到首个事件循环，跨循环复用报错；解法：测试引擎使用 `NullPool`（每 SQL 操作用完即释放），见 `backend/tests/conftest.py`；预防：不要在测试 fixture 中跨函数复用同一引擎到不同循环

#### Scenario: mp-weixin 不支持内联 SVG

- **WHEN** 前端图标方案选 "内联 `<svg>`" 或 `<image src="*.svg">`
- **THEN** 根因：mp-weixin 不渲染 `<svg>` 标签，`<image>` 也不支持 .svg；H5 能渲染但 mp-weixin 空白；解法：用 Unicode 符号 + emoji 经 `<text>` 渲染（`components/ui-icon.vue`），或 CSS `background-image: url("data:image/svg+xml,...")`；预防：跨 H5+mp-weixin 的图标统一走 `<text>` 字形或 iconfont，别用裸 SVG

#### Scenario: 自定义 tabBar 跨平台用 reLaunch

- **WHEN** 需要自定义底栏（如无 PNG 图标资源）且要 H5+mp-weixin 一致
- **THEN** 不配置原生 `tabBar`（`custom:true` 各平台对图标要求不一、易踩坑），改用自研 `components/tab-bar.vue` + `uni.reLaunch` 切换 5 个主页面；代价：切 tab 重载页面（预览可接受）；何时升级：需要保留页面状态/原生切换动画时再切回注册式 custom tabBar

#### Scenario: 本机 curl/uvicorn 调试被 HTTP_PROXY 拦截

- **WHEN** 本机起 uvicorn（127.0.0.1:8000）后 curl 返回 503 空响应，但 `ss` 显示端口在听、日志正常
- **THEN** 根因：环境有 `HTTP_PROXY/HTTPS_PROXY=http://127.0.0.1:10808`，curl 默认走代理，代理返回 503（no_proxy 里的 `127.*` 在某些 curl 版本不生效）；解法：curl 加 `--noproxy '*'`（注意必须引号，否则 bash 通配符展开会挂起）；预防：后端本地联调脚本统一带 `--noproxy '*' --max-time N`

### Requirement: 技巧模式

高效做法 MUST 被记录以促进复用。

#### Scenario: 隔离的集成测试

- **WHEN** 需要写不污染开发数据的后端集成测试
- **THEN** 沿用 conftest 模式：独立测试库 `ey_wall_test` + `NullPool` + function 级 autouse fixture 每测试前 `TRUNCATE` + 每测试新建 Redis 客户端并 flushdb；用户 fixture 已有 `guest_user`/`student_user`/`admin_user` 三档

### Requirement: 文件速查表

高频访问的关键文件 MUST 记录位置，加速导航。

#### Scenario: 定位关键代码

- **WHEN** 需要快速找到某类逻辑
- **THEN** 查阅下表：

| 文件 | 用途 |
|------|------|
| `backend/app/main.py` | FastAPI 应用入口、路由注册、CORS |
| `backend/app/config.py` | `Settings`，所有环境变量集中处 |
| `backend/app/dependencies.py` | FastAPI Depends（DB session、当前用户、限流） |
| `backend/app/utils/zhengfang.py` | 正方教务系统爬虫（RSA 登录、抓 real_name） |
| `backend/app/utils/security.py` | JWT 编解码、密码处理 |
| `backend/app/utils/storage.py` | 存储适配器（local/R2/aliyun） |
| `backend/app/utils/rate_limit.py` | Redis 限流 |
| `backend/app/services/moderation.py` | 异步审核任务调度 |
| `backend/tests/conftest.py` | 测试 fixtures 与隔离策略 |
| `frontend/src/utils/request.ts` | 前端请求封装（JWT 注入、错误码） |
| `frontend/src/utils/storage.ts` | 本地 Token/字典缓存 |
| `SchoolWall.md` | MVP 技术实现文档（原始需求与设计） |
