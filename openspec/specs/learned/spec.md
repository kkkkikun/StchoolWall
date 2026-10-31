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

#### Scenario: OpenSpec proposal 必须用英文标准标题

- **WHEN** `openspec archive` 报非阻塞警告 "Change must have a Why section. Missing required headers. Expected: ## Why and ## What Changes"
- **THEN** proposal.md 必须用英文标题 `## Why` / `## What Changes`（中文「## 为什么做」「## 做什么」不被识别）；解法：写 proposal 时用标准英文标题，正文可中文；archive 仍会成功（非阻塞），但用了标准标题更干净

#### Scenario: 审核重试循环不能折入非微信判定

- **WHEN** 给 `check_post_moderation` 加并联判定层（本地规则/频率）时把合并 verdict 折进 `while verdict == "error"` 重试条件
- **THEN** 根因：verdict 严重度 review(2) > error(1)，本地 review 会让循环立即退出，微信侧 error 重试被静默跳过；解法：本地/频率判定在循环前算一次，循环条件只看微信结果，循环退出后再 `_strictest` 合并；预防：任何"多来源取最严 + 有重试"的管线都要把重试键与合并键分开

#### Scenario: conftest 全表 TRUNCATE 与进程级缓存互斥

- **WHEN** 想给敏感词库这类配置表加进程级/TTL 缓存（含 Redis pubsub 失效）
- **THEN** 根因：测试环境每个用例 TRUNCATE 全部表，进程缓存会跨用例读到脏词库，测试随机漂移；解法：低 QPS 场景直接每次审核读库（"热加载"天然成立），把 loader 做成模块级函数留作未来缓存 seam；预防：凡是注册进 `models/__init__.py` 的表都会被 TRUNCATE，任何缓存测试都要想清楚失效来源

#### Scenario: 字符串锚点补丁器毁坏 import 行

- **WHEN** 用 Python replace 批量给多文件插 import，锚点取的是既有 import 行的**前缀**（如 `from sqlalchemy import`）
- **THEN** 根因：replace 把锚点替换成"锚点+换行+新 import"，而锚点本身是更长 import 行的前缀，导致原行被截成语法错误（`from sqlalchemy import\n... func, select` 漂到新行上）；解法：锚点必须取完整行（含行尾逗号名单），插入后立即 `ast.parse` 逐文件验证；预防：批量脚本化改动后必须全文件语法检查 + 相关测试，绝不裸信"anchor in src" 断言

#### Scenario: ILIKE 转义与通配包装的顺序

- **WHEN** 给已包装成 `%{q}%` 的变量再做 escape_like
- **THEN** 根因：把 `%` 一并转义成字面量，搜索退化为精确含 % 字符的匹配、结果全空；解法：永远对**原始 q** 转义后再包装（`f"%{escape_like(q)}%"`），包装变量只包装一次；预防：引入 escape_like 时全仓 grep `ilike(`，统一"先转义后包装"单一形态

#### Scenario: 图标目录删了、引用没跟着改，底栏图标整体不显示

- **WHEN** 统一图标体系替换了旧图标目录，但某个组件仍写死旧路径
- **THEN** 根因：`<image src>` 指向已删除目录 → 404 → uni-image 渲染为空（底栏只剩文字），而页面级断言通常不覆盖全局组件；解法：所有图标路径一律从 `utils/icons.ts` 注册表取，生成器是唯一来源；预防：重跑生成器后交叉核对「源码引用 / 注册表登记 / 磁盘文件」三者一一对应，缺一即报错
- **THEN** 预防：浏览器侧用 `page.on('response')` 捕获所有 ≥400 的非 API 请求，404 会直接暴露成控制台错误，而不是靠肉眼发现

#### Scenario: 走查断言写死色值，换品牌即失败

- **WHEN** 走查脚本断言 `color in ['rgb(231, 233, 234)', '#e7e9ea']`
- **THEN** 根因：把某个品牌的令牌值固化进断言，换品牌/调暗色即假失败；解法：断言「元素颜色 == 页面上下文里该令牌的计算值」，令牌改了断言不用改；预防：新增断言一律用实测对比度阈值或令牌计算值，禁止写死具体色值

#### Scenario: 静态守卫按品牌色名判定，换品牌即失效

- **WHEN** 静态扫描用「`color: var(--primary)` 即违规」这类规则
- **THEN** 根因：规则隐含假设某个品牌的 `--primary` 恰好不达标，换成达标的品牌后规则要么误报要么漏报；解法：扫描时**解析 App.vue 的令牌实际色值**再算对比度，并额外检查「源码引用的每个令牌都有定义」；预防：守卫只认色值与语义，不认色名

#### Scenario: 生产化短会话与旧本地 .env 不兼容

- **WHEN** 拉入生产化改造后，本地 `app.main` 导入报 `JWT_EXPIRE_MINUTES 应 ≤15`
- **THEN** 根因：代码把会话有效期收紧到 ≤15 分钟（短会话），但本地未跟踪的 `backend/.env` 还留着旧的 7 天值；解法：同步本地环境文件到新契约（本地 .env 不入库，不会污染仓库）；预防：改配置契约后同步核对 `.env.example` 与本地 .env 的键值范围

#### Scenario: 走查静态服务用单线程 TCPServer，偶发 ERR_CONNECTION_CLOSED

- **WHEN** 全页面走查偶发整体 FAIL，控制台报 `Failed to load resource: net::ERR_CONNECTION_CLOSED`，但页面断言全过
- **THEN** 根因：走查脚本用 `socketserver.TCPServer`（单线程、默认 backlog 5）伺服静态产物，Chromium 并发开 6+ 连接时排队的连接被服务端关掉；解法：改用 `http.server.ThreadingHTTPServer`（`scripts/preview.py` 原本即多线程）；预防：所有自建静态服务一律用多线程 + `daemon_threads`，走查偶发失败先查服务端并发再查页面代码

#### Scenario: 组件库默认色悄悄回退，占位符只有 2.30:1

- **WHEN** 管理台输入框占位符实测 2.30:1，主题文件里找不到对应色值
- **THEN** 根因：Element Plus 默认 `--el-text-color-placeholder: #a8abb2`，主题只覆写了主色与语义色，没覆写占位符，浏览器直接回退到组件库默认；解法：亮色改 `#626d7a`（白卡 5.27:1）、暗色改 `#9b9296`（深输入底 5.27:1）；预防：接入组件库时逐个覆写「文字类」令牌并实测对比度，不能只看主色

#### Scenario: 用「文字色」断言去校验「底色」

- **WHEN** 断言「输入框底色应取自 `--bg-card-2`」，实际取到的是 `--text-1` 的颜色
- **THEN** 根因：`assert_token_color()` 比的是 `color`，而底色是 `backgroundColor`，断言对象错了；解法：另加 `assert_token_background()` 比 `backgroundColor`，底色令牌与文字色令牌分开断言；预防：写断言前先确认要校验的是哪个 CSS 属性

#### Scenario: CI 制品带 base 前缀，走查按根路径访问直接白屏

- **WHEN** 管理台走查 34 个场景全部失败，控制台报 `Failed to load module script ... MIME type of "text/html"`
- **THEN** 根因：CI 用 `vite build --base=/admin/` 出制品（nginx 也是 `location /admin/`），产物里资源地址是 `/admin/assets/xxx.js`；走查脚本的静态服务把 `dist/` 挂在根路径，`/admin/assets/...` 落到 SPA 回退返回 `index.html`，浏览器按 `text/html` 拒绝执行模块脚本；解法：走查共享静态服务按 `ADMIN_BASE_PREFIX` 剥离前缀，路由地址同步加前缀；预防：CI 里的浏览器级走查必须针对**与制品完全相同的 base 构建**跑，脚本要显式支持部署前缀

#### Scenario: 同一段代码抄了 11 份，改一处要改 11 个文件

- **WHEN** 11 个管理台走查脚本各带一份完全相同的 `SPAHandler`
- **THEN** 根因：脚本按页面复制粘贴生成，没有共享模块；解法：抽出 `admin-frontend/scripts/walkthrough_server.py` 提供 `create_server()` / `route_url()`，其余脚本只 import；预防：同一段逻辑出现第三次就要抽公共模块，别等抄到第十一份

#### Scenario: 组件库按需引入后，默认主题色反过来盖掉品牌色

- **WHEN** 把 Element Plus 改成按需引入后，全视图走查 34 个场景全挂，界面变回默认蓝，按钮文字对比度从 AA 掉到 2.78:1
- **THEN** 根因：Element Plus 把主题变量定义在 `:root` / `html.dark` 上；全量引入时 `element-plus/dist/index.css` 在 `theme.css` 之前引入所以我们赢，按需引入时组件样式**随组件模块注入**、落在 `theme.css` 之后，同特异性下后加载者胜，默认蓝反盖玫瑰红；解法：把品牌覆写的选择器提到 `html:root`（0,1,1 > `:root` 0,1,0）与 `html.dark:root`（0,2,1 > `html.dark` 0,1,1），与注入顺序解耦；预防：任何「覆写第三方组件库 CSS 变量」的规则都要比对方的特异性更高，别依赖 import 顺序

#### Scenario: 组件被声明出真实类型后，原先被 any 掩盖的类型错全冒出来

- **WHEN** 按需引入后 vue-tsc 报出 42 处「DefaultRow 不能赋给 AdminUser」之类的错误
- **THEN** 根因：此前组件靠 `app.use()` 全局注册，模板里没有类型信息，slot 参数退化成 `any`，类型错被完全掩盖；按需引入会生成 `components.d.ts` 声明真实签名，旧的类型错一次性全部暴露；解法：模板里用 Vue 3.3+ 支持的 `row as X` 标注（`el-table` 不是泛型组件，slot 行类型固定为 `DefaultRow`），el-tag 的状态映射表标注为 `TagProps['type']`；预防：靠全局注册吃到的「类型通过」是假象，组件一旦按需引入就得把真实类型补齐

#### Scenario: 生成式 dts 与类型检查互相卡死

- **WHEN** 新加一个 `el-*` 组件后 `npm run build` 一直失败，dts 永远不更新
- **THEN** 根因：`build` 脚本是 `vue-tsc --noEmit && vite build`，类型检查先跑、失败则构建不执行，而 dts 正是在构建时生成的 —— 死锁；解法：改成 `vite build && vue-tsc --noEmit`（先出 dts 再校验），并把生成的 dts 提交入库；预防：凡是「构建产物驱动类型声明」的链路，类型检查必须在产物生成之后

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
