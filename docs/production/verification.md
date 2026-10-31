# 本地验证与未完成验收

日期：2026-10-30。以下为本次工作区代码的实际检查结果，不代表已上线、已获准上架或已达到容量目标。现有用户界面改动保留；未部署生产或向平台提交审核。

## 已执行

| 检查 | 结果与范围 |
|---|---|
| 后端完整pytest回归 | **529 passed / 156.13秒**，真实隔离PostgreSQL14.24和Redis6.0.16；包含业务、权限、会话、审核、媒体和并发约束。不是目标PostgreSQL15/Redis7环境。 |
| 最后登录/会话定向回归 | **28 passed / 13.74秒**，覆盖生成安全默认昵称、短会话、全历史刷新重放、显式配对、撤销、找回码、管理MFA等；与全量有重叠，不合并计数。 |
| 最后生产配置定向回归 | **18 passed / 1.55秒**，含拒绝长度足够但仍是CHANGE_ME/REPLACE示例值的JWT及指纹密钥。 |
| 最后学生证定向回归 | **20 passed / 6.68秒**，含独立同意、重复认领、到期、清理，以及COS版本/无版本对象/删除标记的模拟测试。最后两个测试晚于全量收集，单独记录；未使用真实学生资料或真实COS。 |
| 运维脚本回归 | **20 passed**，覆盖备份失败不清理、保留顺序、发布证据/回滚/迁移恢复/压测种子保护，以及可信代理真实ASGI来源IP与伪造转发头边界。 |
| 数据库迁移 | 空库到head、上一版本合成用户/微信身份/重复足迹迁移、downgrade一版后重新upgrade及alembic check通过；用户UUID保留、旧认证和原始个人资料清理、足迹留最新。 |
| 逻辑备份恢复 | 合成测试数据库dump并恢复到另一个隔离数据库，核对成功；不是异机PITR、灾难切换或RPO/RTO演练。 |
| API契约 | 最终后端OpenAPI校验通过，**124 paths**；快照release/openapi.json，前端由openapi-typescript生成类型，认证/学生证请求实际引用。 |
| 主前端 | Node22独立运行时：类型检查、H5、微信小程序、Android代码构建通过；单元测试**55 passed**。未产出签名APK。 |
| 管理台 | 类型检查及生产构建通过；单元测试**12 passed**；有大chunk提示，仍需真实运行及加载性能检查。 |
| 依赖 | Python安装与pip check/pip-audit通过；**主前端官方npm audit 0 high / 0 critical**，管理台官方npm audit **0 vulnerabilities**。主前端残余17 moderate + 1 low 全部继承自 `@intlify/core-base` 一条构建期advisory，实测 H5 与微信小程序产物中不含该包。处置明细见[客户端验收记录](../client-release-validation.md)。 |
| 学生端全页面浏览器走查 | **57/57 通过**（`frontend/scripts/all-pages-walkthrough.py`）：`pages.json` 注册的全部 25 个页面 × 亮/暗双模式。逐页断言路由可达、根节点非空、文档级横向溢出、可见文字裁切、WCAG AA文字对比度、控制台错误与未处理异常；**0控制台错误**。 |
| 管理台全视图浏览器走查 | **34/34 通过**（`admin-frontend/scripts/all-views-walkthrough.py`）：全部17个业务路由 × 1280桌面 / 390窄屏，追加布局存在性与文字对比度断言。走查针对 **与制品完全一致的 `--base=/admin/` 构建**执行。 |
| 既有专项走查回归 | 学生端6套（首页/发布/图片上传/详情/登录守卫/桌面平板）与管理台11套（看板/导航/帖子/举报/用户/评论/学生证/申诉/人工审核队列/布局/管理台自身）全部总体PASS。 |
| CI 覆盖补全（2026-10-31） | 此前 CI 只跑 `npm run test:auth`（1 个脚本 / 10 项），6 个前端测试脚本 / 55 项、管理台 12 项、19 套浏览器走查、OpenSpec 校验**全部未进 CI**，刚补齐的回归测试没有自动守护。现已接入：① 前端与管理台**全量**单测；② `npx @fission-ai/openspec@1.4.1 validate --specs`（包名是 `@fission-ai/openspec`，`openspec` 在 npm 上是 0.0.0 占位包）；③ 18 套浏览器走查（7 学生端 + 11 管理台）；④ 客观缺陷扫描 `ui-contrast-audit.py`（起 `scripts/preview.py` 供数）。两份 workflow 经 actionlint 1.7.7 通过。**CI 运行需拉取 Playwright chromium（约 1~2 分钟），本机已实测各步骤命令通过。** |
| 管理台走查与部署前缀对齐（2026-10-31） | CI 用 `vite build --base=/admin/` 出制品、nginx 也是 `location /admin/`，而管理台走查的静态服务把 `dist/` 挂在根路径 → 资源 404 落到 SPA 回退返回 `index.html`，浏览器按 `text/html` 拒绝执行模块脚本，**34 个场景全挂**。已修：抽出共享模块 `admin-frontend/scripts/walkthrough_server.py`（同时消除 11 份重复的 `SPAHandler`），按 `ADMIN_BASE_PREFIX` 剥离前缀、路由地址同步加前缀；实测 `--base=/admin/` 产物下 11 套走查全部 PASS。 |
| 前后端缺陷修复 | ① 夜间模式 `.theme-dark` 只覆写背景令牌、未覆写字色，`verify`/`appeals` 继承亮色近黑字在纯黑底上不可见；② 输入占位符使用 uni 默认 `#808080`（3.95:1）与 `--text-4`（2.64:1）；③ 管理台沿用 Element Plus 默认语义色，标签文字对比度仅2.0~3.1:1。三处均已修复，并由新增对比度断言长期守护。 |
| 图片顺序缺陷 | 发布页并发上传时 `media_ids` 的签发顺序 ≠ 用户选择顺序；后端 `bind_media` 用 `WHERE id IN (...)` 取数、`entity_media` 按 `created_at, id` 排序，用户排好的图片顺序在入库与发布环节丢失。已加 `media_assets.position` 列（迁移 `b7e2c4a91d30`）、`bind_media` 按传入顺序重排并落 position、`entity_media` 按 position 排序，并补后端回归测试与发布页 `data-media-id` 契约断言。**后端用例与迁移需 PostgreSQL 环境执行，本次未在本机运行。** |
| 发布配置 | 两份GitHub workflow通过actionlint1.7.7；生产、备份、监控Compose静态配置校验通过；镜像manifest模板远端只读校验通过。未在本机Docker构建/扫描/启动；Gitleaks与Trivy均未在本地执行，CI保留硬门禁。 |
| 主分支平台化移植（2026-10-31） | 从主题分支把**非 UI 的实现质量**整体移植回主分支：① 后端生产化 31 个新文件 + 全部模型/路由/服务/配置改造 + 迁移 `529bf8becb3f`、`b7e2c4a91d30`（迁移图单根单头、链长21）；② 依赖高危清零（主前端 0 high/0 critical、管理台 0 vulnerabilities）；③ 浏览器级走查体系（全页面/全视图 + 6 套专项）与两个永久审计脚本（`ui-contrast-audit.py`、`ui-perf-audit.py`）；④ 本地预览服务 `scripts/preview.py`（含管理台登录 mock）；⑤ 学生端统一图标体系（183 SVG / 97 语义名，emoji 清零）与语义化设计令牌；⑥ 白天/夜晚双模式主题机制；⑦ 管理台补齐申诉处理/审核任务/学生证认证三视图。**配色沿用主分支自己的玫瑰红品牌**（`--primary: #c2455c`，白字 4.88:1），未引入 X 蓝。**复验**：客观缺陷扫描 25 页 × 亮/暗 —— 对比度 0、点击区 0、小字号 0、横向裁切 0、源码静态守卫 0、**品牌既定例外 0**；全页面走查 57/57、桌面平板 16/16、发布 6/6、图片上传 10/10、登录守卫 11/11、详情互动 33/33、管理台全视图 34/34 + 管理台自身 ui-walkthrough 8/8 全部 PASS；前端单测 55/55、管理台 12/12；type-check 0 错；H5/微信小程序/Android 三端构建通过。**未执行**：后端 pytest 与迁移 upgrade/downgrade（本机无 PostgreSQL/Redis/Docker）、微信开发者工具与真机实测。 |
| 移植过程中发现并修复的既有缺陷 | ① 底栏图标写死 `/static/tabbar/*.svg`，而该目录已随统一图标体系删除 → 底栏 5 个图标全部 404 不显示（页面级断言不覆盖全局组件，肉眼易漏）；改为统一走 `utils/icons.ts` 注册表，并加「源码引用/注册表/磁盘文件」三者一一对应的交叉核对。② 走查脚本把具体色值写死进断言，换品牌即假失败；改为读取令牌计算值判定，与「断言对比度而非色值」的既有规范一致。③ 静态守卫按品牌色名判定、换品牌即失效；改为解析 App.vue 令牌实际色值再算对比度，并新增令牌完整性检查。④ webview 页引用不存在的 `common/link.svg` 导致 404；修正为 `settings/link.svg` 并纳入生成器登记。⑤ 本地未跟踪的 `backend/.env` 仍是旧的 7 天 JWT，与生产化后的短会话契约（≤15 分钟）冲突导致后端无法导入；已同步本地环境文件（不入库）。 |
| 移植收尾复审（2026-10-31） | ① **暗色底栏激活标签是真缺陷不是例外**：原用 `--primary: #c2455c` 压 `--bg-page: #121012` 仅 3.88:1（11.4px 小字需 4.5:1），此前被当作「品牌例外」单列；已改用暗色下提亮的 `--primary-text`（亮 5.81:1 / 暗 6.17:1），并给 5 个底栏图标新增 `primary-dark` 变体（#e07087）使图标与文字同色，**品牌例外由 6 处降为 0 处**。② **18 个走查脚本的静态服务是单线程 `socketserver.TCPServer`**（默认 backlog 5），Chromium 并发开 6+ 连接时偶发 `net::ERR_CONNECTION_CLOSED`，曾把一次全页面走查从 PASS 打成 FAIL；统一改为 `http.server.ThreadingHTTPServer`（`scripts/preview.py` 原本即多线程）。③ 走查里「品牌色例外」仍写死 X 蓝 RGB，移植后已成死代码；改为从 App.vue 的 `--primary*` 令牌读出实际色值注入判定，换品牌仍成立。④ 管理台登录页 logo 仍写死 X 蓝 `#1d9bf0`；改为 `var(--el-color-primary)`。⑤ 首页下拉刷新底色仍是 X 的纯白，与 main 的 `--bg-page: #f7f8fa` 不一致；已对齐。⑥ `ui-walkthrough.py` 用「文字色」断言去校验「输入框底色」，属断言对象错误；新增 `assert_token_background()` 助手并改到正确令牌 `--pill-bg`。⑦ **管理台输入框占位符仍是 Element Plus 默认 `#a8abb2`**（白底仅 2.30:1，低于规范要求的 4.0:1）；主题只覆写了主色与语义色、漏掉占位符；已覆写为亮色 `#626d7a`（5.27:1）、暗色 `#9b9296`（5.76:1）。⑧ **移植时漏带 6 个回归测试文件**（前端 5 个 + 管理台 1 个），`package.json` 引用了它们但磁盘上没有，测试静默跳过；已取回，前端单测从 12 项恢复为 55 项。 |

外部微信、腾讯审核与COS使用模拟边界或SDK形状验证；没有把第三方服务的实际调用、资质或真机行为记为通过。自动化检查不替代人工安全复核。

## 已知发布阻断

主前端官方npm audit：**0 high / 0 critical**（17 moderate + 1 low 告警包，继承自 `@intlify/core-base` 一条构建期advisory，产物中不含该包）；管理台官方npm audit：**0 vulnerabilities**。旧基线里的 braces3.0.3 告警（GHSA-vfj7-8cjw-p6xm）已由**上游撤回该 advisory**，npm 不再下发，braces 本身仍是最新版3.0.3、未发生版本变更；同期新披露的 vue-i18n/@intlify、body-parser、follow-redirects 高危已通过移除未使用的 vue-i18n、回调 @intlify overrides 至9.1.9/9.14.4、overrides body-parser→^1.20.9 与 follow-redirects→^1.16.2 全部清除。详细依赖链、原始报告与解除条件见[客户端验收记录](../client-release-validation.md)。不忽略扫描、不伪造依赖版本。

新增迁移 `b7e2c4a91d30`（media_assets 加 position）已校验 revision 图为单头、链长21、无悬挂引用；**未在真实库执行 upgrade/downgrade**，新增的媒体顺序后端用例也未执行（当前环境无 Docker / PostgreSQL / Redis）。

此外尚未取得：

- 实际主体/备案/社区类目与商店准入、正式隐私政策、SDK清单和可响应的支持渠道。
- 目标PostgreSQL15/Redis7完整CI，真实镜像与密钥扫描，独立越权/隐私数据流复核。
- 本次新增的媒体顺序后端用例与迁移 `b7e2c4a91d30` 尚未在真实隔离PostgreSQL上执行；需在测试库跑通后再勾选。
- 私有COS访问与所有副本删除、腾讯审核故障/额度/费用、进程杀死和真实依赖故障演练。
- 同一制品预发布、应用回滚、异机备份/PITR和真实告警确认；RPO≤1小时、RTO≤4小时仍是目标。
- 1万用户/10万帖/50万评论下100req/s30分钟、200req/s5分钟及8小时长稳，p95与5xx验收；当前不声称承载500在线。
- 正式HTTPS域名的浏览器多标签与跨端联调，微信真机、Android签名包/安装升级/Keystore及SDK隐私行为。
- Web按50→200→全校的真实试运营、平台审核。

完整状态见[交付状态](implementation-status.md)、[发布门禁](release-gates.md)、[证件删除验收](../student-verification.md)。各阶段未执行项保持未勾选，禁止填虚构报告绕过门禁。

## 复验入口

后端：按README设置独立*_test数据库与Redis13/14/15，执行python -m pytest -q；pytest会清理该测试数据。运维：python -m unittest discover -s scripts/tests -v。前端：Node22.12+下npm ci，generate:api、type-check、test、build:h5、build:mp-weixin、build:android；管理台type-check及build。两个前端分别执行官方npm audit。浏览器走查需 Playwright Chromium：先构建产物，再执行 `frontend/scripts/all-pages-walkthrough.py` 与 `admin-frontend/scripts/all-views-walkthrough.py`（另有各页面/视图的专项走查脚本）。迁移与恢复脚本只允许显式ACK的隔离库，见运行手册及CI。

本次临时测试数据库和依赖位于被忽略的.pytest_cache，不属于生产基础设施；回归结束后已关闭55432/56379专用测试进程，未修改开发或生产数据库；私有媒体和证件目录同样已排除版本管理。首次迁移需备份、维护窗口和全员重新登录；旧认证和原始姓名/学号清理不可由downgrade还原。