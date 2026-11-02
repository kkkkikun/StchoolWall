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
| API契约 | 最终后端OpenAPI校验通过，**125 paths**；快照release/openapi.json，前端由openapi-typescript生成类型，认证/学生证请求实际引用。2026-11-01 起新增 `frontend/scripts/api-contract-check.mjs` 漂移守卫（生成类型与契约一致 + 前端/管理台路径字面量都在契约里），已接入 CI。 |
| 主前端 | Node22独立运行时：类型检查、H5、微信小程序、Android代码构建通过；单元测试**55 passed**。未产出签名APK。 |
| 管理台 | 类型检查及生产构建通过；单元测试**12 passed**；有大chunk提示，仍需真实运行及加载性能检查。 |
| 依赖 | Python安装与pip check/pip-audit通过（2026-11-01：pillow 12.3.0 命中 39 条新 advisory，Pillow 13.0.0 要求 Python ≥ 3.11，随 `openspec/changes/backend-python-311/` 升级运行时一并解除）；**主前端官方npm audit 0 high / 0 critical**，管理台官方npm audit **0 vulnerabilities**。主前端残余 **20 moderate**（17 条来自 `@intlify/core-base` 构建期advisory 链、3 条来自 `openapi-typescript` → `@redocly/openapi-core` → `minimatch` 链，0 low），实测 H5 与微信小程序产物中不含相关包。处置明细见[客户端验收记录](../client-release-validation.md)。 |
| 学生端全页面浏览器走查 | **57/57 通过**（`frontend/scripts/all-pages-walkthrough.py`）：`pages.json` 注册的全部 25 个页面 × 亮/暗双模式。逐页断言路由可达、根节点非空、文档级横向溢出、可见文字裁切、WCAG AA文字对比度、控制台错误与未处理异常；**0控制台错误**。 |
| 管理台全视图浏览器走查 | **34/34 通过**（`admin-frontend/scripts/all-views-walkthrough.py`）：全部17个业务路由 × 1280桌面 / 390窄屏，追加布局存在性与文字对比度断言。走查针对 **与制品完全一致的 `--base=/admin/` 构建**执行。 |
| 既有专项走查回归 | 学生端6套（首页/发布/图片上传/详情/登录守卫/桌面平板）与管理台11套（看板/导航/帖子/举报/用户/评论/学生证/申诉/人工审核队列/布局/管理台自身）全部总体PASS。 |
| CI 覆盖补全（2026-10-31） | 此前 CI 只跑 `npm run test:auth`（1 个脚本 / 10 项），6 个前端测试脚本 / 55 项、管理台 12 项、19 套浏览器走查、OpenSpec 校验**全部未进 CI**，刚补齐的回归测试没有自动守护。现已接入：① 前端与管理台**全量**单测；② `npx @fission-ai/openspec@1.4.1 validate --specs`（包名是 `@fission-ai/openspec`，`openspec` 在 npm 上是 0.0.0 占位包）；③ 18 套浏览器走查（7 学生端 + 11 管理台）；④ 客观缺陷扫描 `ui-contrast-audit.py`（起 `scripts/preview.py` 供数）。两份 workflow 经 actionlint 1.7.7 通过。**CI 运行需拉取 Playwright chromium（约 1~2 分钟），本机已实测各步骤命令通过。** |
| 管理台走查与部署前缀对齐（2026-10-31） | CI 用 `vite build --base=/admin/` 出制品、nginx 也是 `location /admin/`，而管理台走查的静态服务把 `dist/` 挂在根路径 → 资源 404 落到 SPA 回退返回 `index.html`，浏览器按 `text/html` 拒绝执行模块脚本，**34 个场景全挂**。已修：抽出共享模块 `admin-frontend/scripts/walkthrough_server.py`（同时消除 11 份重复的 `SPAHandler`），按 `ADMIN_BASE_PREFIX` 剥离前缀、路由地址同步加前缀；实测 `--base=/admin/` 产物下 11 套走查全部 PASS。 |
| 管理台前端体积优化（2026-10-31） | Element Plus 改按需引入（`unplugin-vue-components` + `unplugin-auto-import` 的 `ElementPlusResolver`），只打包实际用到的 41 种 `el-*` 组件与样式。**首屏 411KB → 102KB gzip（-75%）、1458KB → 303KB raw（-79%）；主 chunk 1099KB → 249KB raw；全部 CSS 353KB → 264KB raw / 45KB gzip。** locale 由 `app.use(ElementPlus, {locale})` 改为 `provideGlobalConfig({ locale: zhCn }, app)`，实测 MessageBox 按钮仍为「取消/确定」。npm audit 未新增告警（仍 0 high / 0 critical、3 moderate）。配套修掉四处隐藏问题：① Element Plus 按需注入的组件样式落在品牌主题之后，默认蓝反盖玫瑰红（走查 34/34 全挂、按钮对比度掉到 2.78:1）→ `theme.css` 选择器提到 `html:root` / `html.dark:root`；② 组件被声明出真实类型后暴露 42 处被 `any` 掩盖的类型不匹配 → 模板标注 `row as X`、el-tag 状态映射表标注 `TagProps['type']`；③ 服务型 API 样式落进懒加载视图 chunk、主 chunk 里的 `request.ts` 提示无样式 → 服务型样式改在 `main.ts` 引入；④ 管理台单测用 Node loader 直读源码、绕过了自动注入 → `request.ts` 保留显式 `ElMessage` 导入，样式留在 `main.ts`。新增 `admin-frontend/scripts/style-coverage-check.py` 守护样式齐全（模板用到的组件样式必须存在 + 服务型 API 样式必须在主 chunk），已做负向验证：抽掉主 chunk 的 message 样式即报错，并已接入 CI。 |
| 性能基线与体积门禁（2026-10-31） | 此前性能退化只能人肉看。新增 `frontend/scripts/perf-budget-check.py`（基线 `frontend/perf-baseline.json`）与 `admin-frontend/scripts/bundle-budget-check.py`（基线 `admin-frontend/bundle-baseline.json`），**硬门禁只卡确定性的产物体积**（首屏/全量 JS 与 CSS、最大单块，gzip -9 字节数），超基线 10% 即非零退出；运行时 FCP/DCL/LCP 只采集进报告不拦截（受 runner 负载影响，硬卡会随机失败）。当前基线：学生端首屏 JS 102.9KB gzip / 全量 JS 169.9KB gzip / 全量 CSS 30.5KB gzip；管理台首屏 JS 93.3KB gzip / echarts 块 174.9KB gzip / 全量 JS 483.0KB gzip。两种 `--base` 构建形态均稳定通过。两脚本已接入 CI，均做过负向验证（调小基线即 exit 1）。 |
| 管理台 echarts 按需注册（2026-10-31） | `DashboardView.vue` 原来 `import('echarts')` 整包动态加载。新增 `admin-frontend/src/utils/echarts.ts` 收口注册（`echarts/core` + LineChart + Grid/Tooltip/Legend/AxisPointer 组件 + CanvasRenderer）。**懒加载块 1135.53KB → 526.99KB raw（-54%）、382.15KB → 180.06KB gzip（-53%）**，且仍不进首屏。验证：type-check 通过、看板走查 9/9、全视图走查 34/34，`--base=/admin/` 产物下同样全 PASS。 |
| 管理台类型工具链清除 moderate 告警（2026-11-01） | 管理台 `vue-tsc` 由 `^2.2.0` 升到 `~3.1.8`：`@vue/language-core` 自 **3.0.2** 起改用 `picomatch`、不再依赖 `minimatch`，`minimatch` 连同 `brace-expansion`/`balanced-match`/`de-indent`/`he` 一并从依赖树移除，**官方 npm audit 归零（0 vulnerabilities）**，且**未使用 `overrides` 强行覆盖**（上游条件已兑现，等的就是这一步）。版本选择经过实测：3.0.5 / 3.0.11 / 3.1.8 对本仓库均 0 错，而 3.2.9 / 3.3.14 会误报（3.3.14 在**属性值含 `//`** 时报 `Property 'value' does not exist`，Vue 编译器生成的代码本身正确，属工具侧回归；3.2.9 起报 `:initial-index` 的索引类型错），故锁 `~3.1.8` 不跨到 3.2+。复验：管理台 type-check 0 错、单测 12/12、`build:admin` 通过、样式覆盖守卫通过、体积预算守卫通过（首屏 93.3KB gzip / echarts 块 174.9KB gzip / 全量 JS 483.0KB gzip，与基线一致）、`--base=/admin/` 制品下全视图走查 34/34 PASS。**主前端 20 moderate 未变**（`@intlify/core-base` 与 `@redocly/openapi-core` 两条链等上游，不伪造清零）。该改动只涉及 devDependency，不影响任何客户端产物与后端。 |
| 图标注册表成为唯一来源（2026-10-31） | `frontend-ui` 规范要求「不得手写路径」，实测有 91 个路径（183 处引用、22 个文件）直接写死 `/static/icons/...`。已全部改写为 `ICONS[...]` / `ICON_TONES[...][...]`，并新增 `frontend/scripts/icon-consistency-check.py` 断言磁盘 SVG ↔ 注册表一一对应（207 ↔ 207、208 个语义名）且源码不再出现手写路径，已做两条负向验证（改回手写路径、删掉一个 SVG 均 exit 1）。**说明**：原清单记的「103 个零引用 SVG」经实测不成立 —— 零引用为 0，真实缺口只是「引用没走注册表」。 |
| H5 第三方外呼清零（2026-10-31） | 定位到一个真实缺陷：uni-app H5 框架 CSS 注入 `body:after` 隐藏伪元素，**延迟 3 秒从 dcloud 公网 CDN（cdn.dcloud.net.cn）拉导航阴影图** —— 每次打开页面多一次外网请求，CDN 不可达时控制台报 `net::ERR_CONNECTION_CLOSED`，导致全页面走查随机 FAIL（实测 8 次里偶发 1~2 次，此前一直被当成脚本不稳定）。已用 `html body::after { content: none; animation: none; }` 关掉（比框架的 `body:after` 多一层 html，不依赖样式加载顺序），并新增 `frontend/scripts/external-request-check.py` 断言打开主要页面时无第三方外呼（自家 `/api/v1/**` 后端调用除外）。实测外网请求 **1 条 → 0 条**，已做负向验证（塞一个第三方资源即 exit 1），已接入 CI。 |
| 前后端缺陷修复 | ① 夜间模式 `.theme-dark` 只覆写背景令牌、未覆写字色，`verify`/`appeals` 继承亮色近黑字在纯黑底上不可见；② 输入占位符使用 uni 默认 `#808080`（3.95:1）与 `--text-4`（2.64:1）；③ 管理台沿用 Element Plus 默认语义色，标签文字对比度仅2.0~3.1:1。三处均已修复，并由新增对比度断言长期守护。 |
| 图片顺序缺陷 | 发布页并发上传时 `media_ids` 的签发顺序 ≠ 用户选择顺序；后端 `bind_media` 用 `WHERE id IN (...)` 取数、`entity_media` 按 `created_at, id` 排序，用户排好的图片顺序在入库与发布环节丢失。已加 `media_assets.position` 列（迁移 `b7e2c4a91d30`）、`bind_media` 按传入顺序重排并落 position、`entity_media` 按 position 排序，并补后端回归测试与发布页 `data-media-id` 契约断言。**后端用例与迁移需 PostgreSQL 环境执行，本次未在本机运行。** |
| 发布配置 | 两份GitHub workflow通过actionlint1.7.7；生产、备份、监控Compose静态配置校验通过；镜像manifest模板远端只读校验通过。未在本机Docker构建/扫描/启动；Gitleaks与Trivy均未在本地执行，CI保留硬门禁。 |
| 主分支平台化移植（2026-10-31） | 从主题分支把**非 UI 的实现质量**整体移植回主分支：① 后端生产化 31 个新文件 + 全部模型/路由/服务/配置改造 + 迁移 `529bf8becb3f`、`b7e2c4a91d30`（迁移图单根单头、链长21）；② 依赖高危清零（主前端 0 high/0 critical、管理台 0 vulnerabilities）；③ 浏览器级走查体系（全页面/全视图 + 6 套专项）与两个永久审计脚本（`ui-contrast-audit.py`、`ui-perf-audit.py`）；④ 本地预览服务 `scripts/preview.py`（含管理台登录 mock）；⑤ 学生端统一图标体系（183 SVG / 97 语义名，emoji 清零）与语义化设计令牌；⑥ 白天/夜晚双模式主题机制；⑦ 管理台补齐申诉处理/审核任务/学生证认证三视图。**配色沿用主分支自己的玫瑰红品牌**（`--primary: #c2455c`，白字 4.88:1），未引入 X 蓝。**复验**：客观缺陷扫描 25 页 × 亮/暗 —— 对比度 0、点击区 0、小字号 0、横向裁切 0、源码静态守卫 0、**品牌既定例外 0**；全页面走查 57/57、桌面平板 16/16、发布 6/6、图片上传 10/10、登录守卫 11/11、详情互动 33/33、管理台全视图 34/34 + 管理台自身 ui-walkthrough 8/8 全部 PASS；前端单测 55/55、管理台 12/12；type-check 0 错；H5/微信小程序/Android 三端构建通过。**未执行**：后端 pytest 与迁移 upgrade/downgrade（本机无 PostgreSQL/Redis/Docker）、微信开发者工具与真机实测。 |
| 移植过程中发现并修复的既有缺陷 | ① 底栏图标写死 `/static/tabbar/*.svg`，而该目录已随统一图标体系删除 → 底栏 5 个图标全部 404 不显示（页面级断言不覆盖全局组件，肉眼易漏）；改为统一走 `utils/icons.ts` 注册表，并加「源码引用/注册表/磁盘文件」三者一一对应的交叉核对。② 走查脚本把具体色值写死进断言，换品牌即假失败；改为读取令牌计算值判定，与「断言对比度而非色值」的既有规范一致。③ 静态守卫按品牌色名判定、换品牌即失效；改为解析 App.vue 令牌实际色值再算对比度，并新增令牌完整性检查。④ webview 页引用不存在的 `common/link.svg` 导致 404；修正为 `settings/link.svg` 并纳入生成器登记。⑤ 本地未跟踪的 `backend/.env` 仍是旧的 7 天 JWT，与生产化后的短会话契约（≤15 分钟）冲突导致后端无法导入；已同步本地环境文件（不入库）。 |
| 移植收尾复审（2026-10-31） | ① **暗色底栏激活标签是真缺陷不是例外**：原用 `--primary: #c2455c` 压 `--bg-page: #121012` 仅 3.88:1（11.4px 小字需 4.5:1），此前被当作「品牌例外」单列；已改用暗色下提亮的 `--primary-text`（亮 5.81:1 / 暗 6.17:1），并给 5 个底栏图标新增 `primary-dark` 变体（#e07087）使图标与文字同色，**品牌例外由 6 处降为 0 处**。② **18 个走查脚本的静态服务是单线程 `socketserver.TCPServer`**（默认 backlog 5），Chromium 并发开 6+ 连接时偶发 `net::ERR_CONNECTION_CLOSED`，曾把一次全页面走查从 PASS 打成 FAIL；统一改为 `http.server.ThreadingHTTPServer`（`scripts/preview.py` 原本即多线程）。③ 走查里「品牌色例外」仍写死 X 蓝 RGB，移植后已成死代码；改为从 App.vue 的 `--primary*` 令牌读出实际色值注入判定，换品牌仍成立。④ 管理台登录页 logo 仍写死 X 蓝 `#1d9bf0`；改为 `var(--el-color-primary)`。⑤ 首页下拉刷新底色仍是 X 的纯白，与 main 的 `--bg-page: #f7f8fa` 不一致；已对齐。⑥ `ui-walkthrough.py` 用「文字色」断言去校验「输入框底色」，属断言对象错误；新增 `assert_token_background()` 助手并改到正确令牌 `--pill-bg`。⑦ **管理台输入框占位符仍是 Element Plus 默认 `#a8abb2`**（白底仅 2.30:1，低于规范要求的 4.0:1）；主题只覆写了主色与语义色、漏掉占位符；已覆写为亮色 `#626d7a`（5.27:1）、暗色 `#9b9296`（5.76:1）。⑧ **移植时漏带 6 个回归测试文件**（前端 5 个 + 管理台 1 个），`package.json` 引用了它们但磁盘上没有，测试静默跳过；已取回，前端单测从 12 项恢复为 55 项。 |

外部微信、腾讯审核与COS使用模拟边界或SDK形状验证；没有把第三方服务的实际调用、资质或真机行为记为通过。自动化检查不替代人工安全复核。

## Production CI 实测证据（2026-11-02）

本节是 **GitHub Actions「Production CI」（`.github/workflows/ci.yml`）的真实运行结果**，不是本地复跑。本机不运行 PostgreSQL/Redis，CI 是后端与镜像的唯一权威；下列命令、环境与结果逐条取自 CI 日志，可按运行链接核对。

### 环境与来源

| 项 | 值 |
|---|---|
| 工作流 | Production CI（`.github/workflows/ci.yml`），`verify` + `image` 两个作业 |
| 运行 | `41369377491`（push 到 main，提交 `917dd7b5f0966ab140fc1b47dfc2b531c98e997f`，2026-11-02 00:51 UTC 起）→ <https://github.com/kkkkikun/StchoolWall/actions/runs/41369377491> |
| 运行器 | `ubuntu-latest`（GitHub 托管） |
| Python | **3.11.17**（`actions/setup-python@v5`，`python-version: "3.11"`） |
| 服务容器 | `postgres:15-alpine`（库 `ey_wall_test`）、`redis:7-alpine`（库 14/15）；`pg_isready`/`redis-cli ping` 健康检查通过 |
| 环境变量 | `ENVIRONMENT=test`，`DATABASE_URL`/`TEST_DATABASE_URL` 指向 `127.0.0.1:5432/ey_wall_test`，`REDIS_URL`/`TEST_REDIS_URL` 指向 `redis://127.0.0.1:6379/14`、`/15` |
| 结论 | `verify` **成功**（全部步骤通过）；`image` **失败**（Trivy 扫描步骤退出码 1） |

### verify 作业：后端全量门禁（全部通过）

| 命令 | 结果 |
|---|---|
| `python -m pip install -r backend/requirements.txt pip-audit` | 成功 |
| `cd backend && python -m pytest -q` | **535 passed, 3 skipped in 210.88s**（真实 PostgreSQL 15 + Redis 7） |
| `python -m unittest discover -s scripts/tests -v` | 运维脚本回归 **20 项全 ok** |
| `python scripts/check_migrations.py`（`MIGRATION_TEST_ACK=YES_ISOLATED_DATABASE`，隔离库 `ey_wall_migration`） | 空库 upgrade → `b7e2c4a91d30` → downgrade → `529bf8becb3f` → 再 upgrade → `alembic check` 输出 `No new upgrade operations detected`；末行 **`Migration cutover, rollback/re-upgrade and metadata consistency: PASS`**，并记录 `legacy UUID/password identities preserved; old verification/PII invalidated; newest footprint retained` |
| `POSTGRES_TEST_CONTAINER=<pg service id> python scripts/check_restore.py` | `Synthetic logical restore matched rows, identities and schema version: {'users': 4, 'login_identities': 3, 'posts': 1, 'footprints': 1, 'jobs': 0, 'student_verifications': 0}`；末行 `Logical restore smoke PASS; this is not off-host PITR/RPO/RTO evidence` |
| `cd backend && python ../scripts/check_api_contract.py --output ../release/openapi.json` | **`contract validated: 125 paths`**，契约导出到 `release/openapi.json` 并随制品上传 |
| `pip-audit -r backend/requirements.txt --strict` | **`No known vulnerabilities found`**（Pillow 13.0.0 的 39 条 advisory 随 Python 3.11 升级一并解除，未豁免任何条目） |
| Gitleaks 密钥扫描（`gitleaks/gitleaks-action`） | 通过 |
| 前端/管理台 type-check、单测、三端构建、`npm audit --audit-level=high` | 通过 |
| `npx @fission-ai/openspec@1.4.1 validate --specs` | `Totals: 7 passed, 0 failed (7 items)` |
| 图标一致性、管理台样式覆盖、前后端体积预算、18 套浏览器走查（7 学生端 + 11 管理台）、客观 UI 缺陷审计 | 通过 |

据此，`openspec/changes/backend-python-311/tasks.md` 第 8 行「Production CI：PostgreSQL 15 + Redis 7 上的后端全量 pytest、迁移 upgrade/downgrade、API 契约导出与 pip-audit 硬门禁全部通过」**证据已取得，予以勾选**。注意这不等于异机 PITR/RPO/RTO 演练，也不等于独立人工安全复核。

### image 作业：构建与导入冒烟通过，Trivy 扫描失败

| 步骤 | 结果 |
|---|---|
| `Use the exact tested Python dependency constraints` | 通过（CI 注入 `python -m pip freeze` 的约束并校验 sha256） |
| `Build once`（`backend/Dockerfile`，基础镜像 `python:3.11-slim`） | **通过**，产出 `schoolwall-ci:917dd7b5f0966ab140fc1b47dfc2b531c98e997f`（镜像 digest `sha256:aa19d49a…`，Debian 13.7） |
| `Smoke exact built image before push` | **通过**：`docker run --rm --network=none --entrypoint python …` 输出 `built image imports and exports contract` |
| `Scan exact production image before push`（Trivy，`severity=CRITICAL,HIGH`、`exit-code=1`、`ignore-unfixed=false`） | **失败（exit code 1）**：OS 层 **46 条 HIGH / 0 CRITICAL**，python-pkg 层 **2 条 HIGH / 0 CRITICAL** |
| `Push verified image and resolve immutable digest` | **未执行**（扫描失败即中止）——带高危的镜像没有被推送 |

Trivy 明细（均为 HIGH，无 CRITICAL）：

- **OS 层 46 条**：`util-linux` 家族（`bsdutils`、`libblkid1`、`liblastlog2-2`、`libmount1`、`libsmartcols1`、`libuuid1`、`login`、`mount`、`util-linux`）的 `CVE-2026-76642`、`CVE-2026-78408`、`CVE-2026-78409`、`CVE-2026-78410`；`libacl1` 的 `CVE-2026-54369`；`libncursesw6`/`libtinfo6`/`ncurses-base` 的 `CVE-2025-69720`；`libsqlite3-0` 的 `CVE-2026-119373`、`CVE-2026-119586`；`libsystemd0`/`libudev1` 的 `CVE-2026-16742`；`perl-base` 的 `CVE-2026-9538`。**这 46 条的 Fixed Version 列为空**（状态为 `affected` / `fix_deferred`），即 Debian 13 当前没有可用修复版本。
- **python-pkg 层 2 条**：来自基础镜像自带的 `setuptools 79.0.1` 内置副本 —— `setuptools/_vendor/jaraco.context 5.3.0`（`CVE-2026-23949`，修复版本 6.1.0）与 `setuptools/_vendor/wheel 0.45.1`（`CVE-2026-24049`，修复版本 0.46.2）。站点层的 `wheel 0.46.3`、`Pillow 13.0.0` 及其余应用依赖均为 0 条。这两条已在 `backend/Dockerfile` 内清理，见下节「镜像内 setuptools 高危清理」。

**根因**：`backend/Dockerfile` 直接以 `python:3.11-slim`（Debian 13.7）为底，既没有做 OS 安全更新，也没有清理镜像内自带的构建工具 `setuptools`（其内置的 `jaraco.context`/`wheel` 副本带两条可修复的 HIGH —— 这两条已在下一节清理）。Trivy 门禁按仓库既定规则 `severity=CRITICAL,HIGH` + `ignore-unfixed=false`，因此 Debian 侧尚无修复版本的 46 条 HIGH 同样判失败 —— **未做豁免**：没有加 `.trivyignore`、没有把 `ignore-unfixed` 改成 true、没有下调 severity 门禁。

**处置**：`openspec/changes/backend-python-311/tasks.md` 第 9 行「image 作业（仅 main 分支）：`python:3.11-slim` 基础镜像构建、导入冒烟与 Trivy 扫描通过」**保持未勾选**。清除该门禁需要下列之一，且都属于运维/产品决策，不在本次证据记录的授权范围内：① 等 Debian 发布对应安全更新后重建镜像（可自主重跑验证）；② 改用不含 `util-linux`/`ncurses`/`perl-base`/`libsystemd0` 的镜像族（属基础镜像族级变更，须走 `openspec/changes/` 提案）。其中镜像内 `setuptools` 自带的两条 HIGH 属仓库自控范围，已在 `backend/Dockerfile` 内单独清理（见下节），其「python-pkg 层 0 HIGH」的权威证据待合并后 main 分支的 image 作业复跑给出。

## 镜像内 setuptools 高危清理（2026-11-02）

**目标**：清掉 Production CI `image` 作业 Trivy **python-pkg 层**的 2 条 HIGH —— 基础镜像自带 `setuptools 79.0.1` 的内置副本 `jaraco.context 5.3.0`（`CVE-2026-23949`，修复版本 6.1.0）与 `wheel 0.45.1`（`CVE-2026-24049`，修复版本 0.46.2）。基础镜像 **OS 层的 46 条无修复版本 HIGH** 属镜像族级变更，不在本次仓库自控范围内（处置见上节与下节末段）。

**改动**：只改 `backend/Dockerfile` 的依赖安装层 —— 装完依赖后在**同一层内**执行 `pip uninstall --yes setuptools wheel`，并断言 `pip list --format=freeze` 里不再出现 `setuptools`/`wheel`（残留即构建失败）。两者都是构建期工具，运行期不需要；移除后 `setuptools/_vendor/` 下的 `jaraco.context-5.3.0.dist-info` 与 `wheel-0.45.1.dist-info` 一并消失，Trivy 无从再报这两条。因为删除发生在安装层内部，被移除的文件不会留在任何镜像层里。未改 `backend/requirements.txt` 的应用依赖版本，未改业务代码，未加 `.trivyignore`、未把 `ignore-unfixed` 改成 true、未下调 severity。

**根因复核（本地离线核对）**：`pip download --no-deps setuptools==79.0.1` 解包后，`setuptools/_vendor/` 下确有 `jaraco.context-5.3.0.dist-info` 与 `wheel-0.45.1.dist-info`，与 Trivy 报告的 `jaraco.context (METADATA) 5.3.0` / `wheel (METADATA) 0.45.1` 逐条对应（站点层的 `wheel 0.46.3` 不在告警内），确认这两条 HIGH 的来源就是基础镜像自带的 `setuptools`。

| 命令 | 环境 | 结果 |
|---|---|---|
| `pip download --no-deps setuptools==79.0.1` 后解包查看 `setuptools/_vendor/*.dist-info` | 本机 Ubuntu（WSL），Python 3.10.12，官方 PyPI | `jaraco.context-5.3.0.dist-info`、`wheel-0.45.1.dist-info` —— 根因确认 |
| 临时 venv 内 `pip install setuptools==79.0.1 wheel` → `pip uninstall --yes setuptools wheel` → `pip list --format=freeze \| grep -qiE '^(setuptools\|wheel)=='` | 同上 | 卸载退出码 0（未安装时只输出 `WARNING: Skipping … as it is not installed`，仍为 0）；断言通过；随后 `import setuptools` / `import pkg_resources` 均为 `ModuleNotFoundError` |
| 完整复刻 `backend/Dockerfile` 安装层的 shell 链（`if/else` 装依赖 → 卸载 → 断言），`sh -n` 语法检查 + 实跑 | 同上 | `sh -n` 通过；实跑链路退出码 0，装依赖失败时链路同步失败（构建不会被静默放过） |
| 后端导入冒烟：注入 `meta_path` 阻断 `setuptools`/`pkg_resources`/`_distutils_hack` 后 `from app.main import app` | 仓库共享 venv（Python 3.10.12） | 导入成功并导出 **125 paths** —— 运行期不依赖 setuptools |
| `grep -rn "pkg_resources"` 扫描已装依赖与 `tencentcloud-sdk-python==3.1.188`、`cos-python-sdk-v5==1.9.44` 官方 wheel | 同上 | 运行期依赖均不 import `pkg_resources`（命中项只在测试夹具、pytest/alembic 测试辅助与文档字符串里） |

**未取得 / 未完成**：本机没有 Docker，本地无法构建镜像或执行 Trivy；`image` 作业只在 main 分支运行，因此「python-pkg 层 0 HIGH」的权威证据须由**合并后 main 分支的 Production CI image 作业**给出（Trivy 报告里 `Python (python-pkg)` 一节应为 `Total: 0`），且该次运行仍会因 OS 层 46 条 HIGH 退出码 1 —— 那是 Debian 13 尚无修复版本所致，属预期而非本次改动引入的回归。OS 层 46 条 HIGH 需等 Debian 上游发布安全更新后重建镜像，或改用不含 `util-linux`/`ncurses`/`perl-base`/`libsystemd0` 的镜像族（属基础镜像族级变更，须走 `openspec/changes/` 提案与人工决策，本次未擅自更换）。据此 `openspec/changes/backend-python-311/tasks.md` 第 9 行**保持未勾选**。

## G3 容量实测（2026-11-02，隔离环境）

本节是 **发布门禁 G3 的第一次真实数值取证**，环境为仓库外的隔离目录，**未接触生产域名、真实学生数据、开发库或生产 Redis**。原始数值、命令与环境见[容量基线与压测](capacity.md)；本节只记录验证口径、判定与未完成项。

### 环境与命令

| 项 | 值 |
|---|---|
| 代码版本 | commit `9945322ddb2b994ac42fd9e990c1ea4e7c78193f`（main，PR #15 之后） |
| 镜像 digest | **无**：本机无 Docker，实测为源码直跑 |
| 宿主 | WSL2 / Ubuntu 22.04.5，AMD Ryzen 7 8845H（8C/16T），内存 11.6 GB（共享笔记本，另有无关进程共跑，swap 已占满） |
| 数据库 | 本机独立 PostgreSQL 15.19 实例（端口 55433），专用库 `schoolwall_loadtest` |
| 缓存 | 源码编译的独立 Redis 7.2.5 实例（端口 6399），专用逻辑库 **13** |
| 压测工具 | k6 v2.3.0（GitHub 官方 release 二进制） |
| 应用 | uvicorn 4 worker（127.0.0.1:8000）+ 后台 worker 1 进程；`ENVIRONMENT=test`；依赖按 `backend/requirements.txt` 锁定版本安装（Pillow 用 12.3.0 代替 13.0.0，因 13.0.0 要求 Python ≥ 3.11 而本机只有 3.10.12） |
| 建库与播种 | `python -m alembic upgrade head` → `ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE python ../scripts/load/seed.py --users 10000 --posts 100000 --comments 500000`（耗时 37 秒；产出 10000 合成用户 / 100000 帖 / 500000 评论） |
| 发压命令 | `ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION ALLOWED_LOAD_HOST=127.0.0.1 BASE_URL=http://127.0.0.1:8000 PROFILE=steady RATE=100 DURATION=30m k6 run scripts/load/campus.js`（burst / soak 同形换 `PROFILE`、`RATE`、`DURATION`） |

守卫未放宽：`scripts/tests/test_load_seed_guard.py` 与整套 `scripts/tests`（20 项）本地全绿；种子的三重限制（`ENVIRONMENT=test`、`*_loadtest` 库名、显式 ACK）与「拒绝已有帖子的数据库」保护原样生效（正式取证前先 `DROP DATABASE` 重建库再播种）。9 小时测试 token 与 `accounts.json` 写在隔离运行目录（权限 0600），**未入库、未进 CI 制品、未写日志**，报告只记录数量与签发方式。

### 判定

| 场景 | 结果 |
|---|---|
| steady 100req/s × 30 分钟 | 读 p95 **435.26ms**、写 p95 **147.42ms**、业务成功率 **100.00%**、5xx **0.00%**、429 **0 次**、dropped iterations **16** —— 延迟与成功率达标，**「无 dropped iterations」未达标** |
| burst 200req/s × 5 分钟 | 实际 **167.36 req/s**、读 p95 **2743.72ms**、写 p95 **4063.85ms**、业务成功率 99.996%、5xx 0%、dropped iterations **9624** —— **未通过** |
| soak 100req/s × 8 小时 | 取证进行中（见[容量基线与压测](capacity.md)） |

**G3 保持未通过**：`docs/production/release-gates.md` 的 G3 行不改写为已通过。根因已定位到**热点帖单行写锁队列**——详情页 `view_count` 自增（`backend/app/services/post.py:208`）与点赞路径的 `SELECT ... FOR UPDATE` 都写同一行，场景里 80% 详情集中在单帖即把该行变成全局串行点；PostgreSQL 日志记录到同一 tuple 上最长 38 个进程的锁等待队列与数千条 `>500ms` 慢语句。

### 已知限制与剩余人工前置条件

1. **runner 限制**：宿主是共享的 WSL2 笔记本，11.6 GB 内存且 swap 已占满、另有无关进程共跑；压测期间虚拟机曾被整体冻结 70.2 分钟（采样时间轴 `04:01:55Z → 05:12:10Z`）。k6 场景计时随虚拟机停摆，故各场景**有效负载时长**成立，但墙钟被消耗、9 小时 token 会提前到期，冻结瞬间的在途请求会产生 503 与极端耗时。跨冻结窗口的那一轮 steady **不作为正式记账**。
2. **硬件不是生产等价**：16 线程笔记本 + 单实例 PG/Redis + 同机发压，与生产拓扑不同；上述数值只能作为同机基线，不能当作容量承诺。
3. **依赖版本**：本机只有 Python 3.10.12，无法复现 CI/生产的 Python 3.11.17 + Pillow 13.0.0 组合（Pillow 13.0.0 要求 ≥3.11），FastAPI/Starlette/uvicorn/SQLAlchemy/asyncpg/redis 均按锁定版本安装。
4. **第三方边界**：本次只测可观测的本地处理能力；审核供应商与 COS 使用可控 stub，**未消耗真实审核额度、未验证真实供应商吞吐**；`docs/production/capacity.md` 要求的「真实认证→会话刷新、上传→隔离→审核→发帖、组局最后名额竞争、重复请求、发布期间流量、停worker重启、DB/Redis/审核超时与断网恢复」等补充场景只覆盖了「停 worker 重启」一项，其余未执行。
5. **仍需人工/专用环境**：专用压测服务器（独占内存与磁盘）、生产等价 PostgreSQL 15 + Redis 7 拓扑、8 小时长稳在无冻结环境复跑、以及本文档列出的补充场景。

## 已知发布阻断

主前端官方npm audit：**0 high / 0 critical**（20 moderate 告警包：17 条继承自 `@intlify/core-base` 的构建期advisory 链、3 条来自 `openapi-typescript` → `@redocly/openapi-core` → `minimatch` 链，均为 devDependency 传递依赖，产物中不含该包）；管理台官方npm audit：**0 vulnerabilities**（2026-11-01，`vue-tsc` 升至 `~3.1.8` 后 `minimatch` 依赖链消失）。旧基线里的 braces3.0.3 告警（GHSA-vfj7-8cjw-p6xm）已由**上游撤回该 advisory**，npm 不再下发，braces 本身仍是最新版3.0.3、未发生版本变更；同期新披露的 vue-i18n/@intlify、body-parser、follow-redirects 高危已通过移除未使用的 vue-i18n、回调 @intlify overrides 至9.1.9/9.14.4、overrides body-parser→^1.20.9 与 follow-redirects→^1.16.2 全部清除。详细依赖链、原始报告与解除条件见[客户端验收记录](../client-release-validation.md)。不忽略扫描、不伪造依赖版本。2026-11-01 新披露的 39 条 pillow advisory 全部指向 13.0.0，而 13.0.0 要求 Python ≥ 3.11（12.3.0 是最后一个支持 3.10 的版本），因此在 Python 3.10 上没有可用修复版；按 G1 规则严重与高危漏洞不得豁免，处理方式是升级运行时到 3.11（见 `openspec/changes/backend-python-311/`），不做风险豁免、不加忽略扫描配置。

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