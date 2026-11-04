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

> **2026-11-03 补记**：上述「python-pkg 层 0 HIGH」的权威证据**已取得** —— 见下节「Production CI image 作业 Trivy 复跑取证（2026-11-03）」：运行 `41578409185` 的 Trivy 报告里 65 个 `python-pkg` 目标逐条为 0，全表 `Total: 45 (HIGH: 45, CRITICAL: 0)` 全部来自 `debian 13.7` 的 OS 层。第 9 行仍**保持未勾选**，因为 OS 层的无修复版本 HIGH 仍在、Trivy 退出码 1。

## Production CI image 作业 Trivy 复跑取证（2026-11-03）

本节是 **上一节「python-pkg 层 0 HIGH」权威证据缺口**的实测结果：main 分支 `image` 作业在合并 `backend/Dockerfile` 的 setuptools/wheel 清理之后复跑，取回了该次运行的**原始日志**，据此逐条核实导入冒烟与 Trivy 报告。

### 运行来源

| 项 | 值 |
|---|---|
| 运行 | `41578409185`（push 到 main，提交 `e5047094b58b3d6d14f35c407c7323f79c41051c`，2026-11-03 04:29 UTC 起）→ <https://github.com/kkkkikun/StchoolWall/actions/runs/41578409185> |
| image 作业 | job id `125732883940`，`2026-11-03T04:47:45Z → 04:49:09Z`，**结论 failure**，原始日志 1671 行 |
| 扫描对象 | `schoolwall-ci:e5047094b58b3d6d14f35c407c7323f79c41051c`（`debian 13.7`） |
| 扫描配置 | `aquasecurity/trivy-action@v0.36.0`（`ed142fd0`），`severity=CRITICAL,HIGH`、`exit-code=1`、`ignore-unfixed=false` —— **与 2026-11-02 完全一致，未豁免、未降门禁** |

取日志的命令与本机限制：执行环境只放通了 GitHub 的 API 与代码托管域名，Actions 日志所在的 blob 存储域名在本机 TLS 握手超时（`gh run view <run> --log`、`gh api repos/…/actions/jobs/<id>/logs` 均无法落地），因此由 GitHub 自己的 runner 取回该作业日志并把原始片段贴到 PR #30 评论；本节引用的行号即该评论中带行号的原始日志行。

### image 作业步骤结论（GitHub API）

| # | 步骤 | 结论 |
|---|---|---|
| 4 | Use the exact tested Python dependency constraints | success |
| 8 | Build once | success |
| 9 | Smoke exact built image before push | **success** |
| 10 | Scan exact production image before push（Trivy） | **failure** |
| 11 | Push verified image and resolve immutable digest | skipped（扫描失败即中止，镜像未推送） |

### 三项核实结果

1. **导入冒烟仍打印契约行** —— 原始日志第 `2026-11-03T04:48:29.3409646Z` 行：`built image imports and exports contract`（步骤 `Smoke exact built image before push` 结论 success）。
2. **python-pkg 层 0 条** —— Trivy `Report Summary` 表里，唯一的 `debian` 目标记 **45**，而 **65 个 `python-pkg` 目标逐条记 0**（`SQLAlchemy`、`alembic`、`boto3`、`cryptography`、`fastapi`、`httpx`、`pydantic`、`requests`、`urllib3`、`uvicorn` 等站点包全部为 `0`），全表合计 `Total: 45 (HIGH: 45, CRITICAL: 0)`，与 `debian` 那一行的 45 相等 ⇒ **python-pkg 层 HIGH 0 条 / CRITICAL 0 条**。2026-11-02 报出的 `setuptools/_vendor` 内置副本两条（`jaraco.context 5.3.0` → `CVE-2026-23949`、`wheel 0.45.1` → `CVE-2026-24049`）在本次报告中**不再出现**；整份日志里 `setuptools`/`wheel`/`jaraco`/`_vendor` 只出现在 Dockerfile 的构建命令行本身，没有任何一条扫描命中。
3. **OS 层的无修复版本 HIGH 仍在** —— `debian 13.7` 目标仍有 **45 条 HIGH、0 CRITICAL**（较 2026-11-02 记录的 46 条少 1 条：本次报告里不再出现 `libsqlite3-0` 的 `CVE-2026-119586`，`CVE-2026-119373` 仍在）。明细表可见 44 行、17 个库（`util-linux` 家族 9 个库 × 4 条 `CVE-2026-76642/78408/78409/78410`、`libacl1` `CVE-2026-54369`、`libncursesw6`/`libtinfo6`/`ncurses-base` `CVE-2025-69720`、`libsqlite3-0` `CVE-2026-119373`、`libsystemd0`/`libudev1` `CVE-2026-16742`、`perl-base` `CVE-2026-9538`），**Fixed Version 列全部为空**（状态 `affected` / `fix_deferred`，即 Debian 13 当前没有可用修复版本）；控制台表格中 `ncurses-bin` 一行的单元格为空，故明细可见 44 条而汇总为 45 条。Trivy 步骤因此以 `##[error]Process completed with exit code 1.` 结束。

### 结论与未解除项

- **仓库自控部分已达成**：镜像内 python-pkg 层 HIGH 清零，原始证据为运行 `41578409185` 的 Trivy `Report Summary`（65 个 python-pkg 目标全为 0）。
- **门禁仍未解除**：OS 层 45 条无修复版本 HIGH 使 Trivy 退出码 1，`image` 作业失败、带高危的镜像未推送，`openspec/changes/backend-python-311/tasks.md` 第 9 行**保持未勾选**，发布门禁 **G1 未解除**。
- **未做的动作**：没有加 `.trivyignore`、没有改 severity、没有把 `ignore-unfixed` 改成 true、没有改 `backend/requirements.txt` 与业务代码、没有换基础镜像族（属人工决策）。解除 OS 层 HIGH 仍只有两条路：等 Debian 上游发布安全更新后重建镜像（可自主重跑验证），或走 `openspec/changes/` 提案换用不含 `util-linux`/`ncurses`/`perl-base`/`libsystemd0` 的镜像族（须人工决策）。

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
| soak 100req/s × 8 小时 | **中止于 7h22m30s（8 小时的 92%）**：有效速率 99.61 req/s、全部请求 p50/p95/p99 = 32.82ms / **467.04ms** / 732.82ms、5xx **1,355** 次、429 **47,158** 次单列、dropped iterations **10,187** —— 时长未达 8 小时，且「无 dropped iterations」未达标，**不作为正式长稳报告记账**（见[容量基线与压测](capacity.md)） |

**G3 保持未通过**：`docs/production/release-gates.md` 的 G3 行不改写为已通过。根因已定位到**热点帖单行写锁队列**——详情页 `view_count` 自增（`backend/app/services/post.py:208`）与点赞路径的 `SELECT ... FOR UPDATE` 都写同一行，场景里 80% 详情集中在单帖即把该行变成全局串行点；PostgreSQL 日志记录到同一 tuple 上最长 38 个进程的锁等待队列与数千条 `>500ms` 慢语句。

soak 一轮的中止与该瓶颈无关：承载压测的宿主上，dsh-superagent 服务被停止时终止了自己的子进程树，把仍在运行的 k6 一并带走，该轮在 7 小时 22 分 30 秒（92%）被 SIGTERM 终止。中止前的数值可作为部分实测参考留档，但按「未达 8 小时的 soak 不得按正式报告记账」的口径不计入正式验收，**G3 仍未通过**。

> 本节保留为 2026-11-02 那轮的历史记录。热点帖单行写锁瓶颈消除后的复测（burst、soak 跑满 8 小时、steady 补跑、名额竞争与任务恢复）见下一节「G3 容量复测（2026-11-03，专用隔离环境，热点帖单行写锁修复后）」，G3 的当前判定以该节与 `docs/production/release-gates.md` 的 G3 行为准。

### 已知限制与剩余人工前置条件

1. **runner 限制**：宿主是共享的 WSL2 笔记本，11.6 GB 内存且 swap 已占满、另有无关进程共跑；压测期间虚拟机曾被整体冻结 70.2 分钟（采样时间轴 `04:01:55Z → 05:12:10Z`）。k6 场景计时随虚拟机停摆，故各场景**有效负载时长**成立，但墙钟被消耗、9 小时 token 会提前到期，冻结瞬间的在途请求会产生 503 与极端耗时。跨冻结窗口的那一轮 steady **不作为正式记账**。
2. **硬件不是生产等价**：16 线程笔记本 + 单实例 PG/Redis + 同机发压，与生产拓扑不同；上述数值只能作为同机基线，不能当作容量承诺。
3. **依赖版本**：本机只有 Python 3.10.12，无法复现 CI/生产的 Python 3.11.17 + Pillow 13.0.0 组合（Pillow 13.0.0 要求 ≥3.11），FastAPI/Starlette/uvicorn/SQLAlchemy/asyncpg/redis 均按锁定版本安装。
4. **第三方边界**：本次只测可观测的本地处理能力；审核供应商与 COS 使用可控 stub，**未消耗真实审核额度、未验证真实供应商吞吐**；`docs/production/capacity.md` 要求的「真实认证→会话刷新、上传→隔离→审核→发帖、组局最后名额竞争、重复请求、发布期间流量、停worker重启、DB/Redis/审核超时与断网恢复」等补充场景只覆盖了「停 worker 重启」一项，其余未执行。
5. **仍需人工/专用环境**：专用压测服务器（独占内存与磁盘）、生产等价 PostgreSQL 15 + Redis 7 拓扑、8 小时长稳在无冻结环境复跑、以及本文档列出的补充场景。
6. **soak 中止的处置**：该轮 7h22m30s 的数值已按上文写进 `docs/production/capacity.md` 作为部分实测参考，但**不作为正式 8 小时长稳报告**。复跑时须保证压测进程与宿主上的常驻服务进程树解耦（例如把压测环境与 agent 服务分机部署，或让 agent 不持有压测进程的后台作业），避免再出现「停服务连带终止压测」的情况。

## G3 容量复测（2026-11-03，专用隔离环境，热点帖单行写锁修复后）

本节记录**消除热点帖单行写锁瓶颈后的复测**。环境为仓库外的隔离目录（专用 KVM 虚拟机 + 容器化 PostgreSQL 15 / Redis 7），**未接触生产域名、真实学生数据、开发库或生产 Redis**。原始数值与环境见[容量基线与压测](capacity.md)。

### 环境与命令

| 项 | 值 |
|---|---|
| 代码版本 | commit `2757118`（分支 `agent/fix-post-row-lock-1e6521eb2722`） |
| 镜像 digest | `schoolwall-loadtest@sha256:0bd2b931870eac06094c139b0241fea417c6972384b24985300c95c69959ce67`（由 `backend/Dockerfile` 构建；基础镜像与 pip 均走镜像站，Dockerfile 与 CI 同源） |
| 宿主 | KVM 虚拟机 / Ubuntu 24.04.5 LTS，128 vCPU、295 GB 内存、根盘 991 GB；**专用环境，无宿主冻结、无进程树干扰** |
| 数据库 / 缓存 | PostgreSQL 15.14（容器，端口 55433，专用库 `schoolwall_loadtest`）/ Redis 7.4.7（容器，端口 6399，逻辑库 13） |
| 压测工具 | k6 v0.57.0（源码构建，Go 1.22.2），脚本 `scripts/load/campus.js` |
| 应用 | 镜像内 Python 3.11 + `backend/requirements.txt` 锁定依赖；uvicorn 4 worker + 后台 worker 1 进程；`DB_POOL_SIZE=10`、`DB_MAX_OVERFLOW=5`（连接预算 75 < `max_connections=100`） |
| 建库与播种 | `DROP DATABASE` 重建 → `python -m alembic upgrade head` → `ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE python ../scripts/load/seed.py --users 10000 --posts 100000 --comments 500000`（10000 合成用户 / 100000 帖 / 500000 评论） |
| 发压命令 | `ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION ALLOWED_LOAD_HOST=127.0.0.1 BASE_URL=http://127.0.0.1:8000 PROFILE=burst RATE=200 DURATION=5m k6 run scripts/load/campus.js`；soak 同形换 `PROFILE=soak RATE=100 DURATION=8h`，并以 `setsid` 脱离会话进程组启动（避免会话结束连带终止压测）；steady 补跑为 `PROFILE=steady RATE=100 DURATION=30m`，同样 `setsid` 启动 |
| 凭证续签 | 种子的 9 小时测试 token 在 soak 结束后已过期；steady 补跑前按 `scripts/load/seed.py` 同一签发方式（新建 `user_sessions` + `create_access_token`，9 小时有效期）在隔离库内重新签发，写入隔离运行目录的私有文件，**不入库、不进 CI 制品、不写日志** |
| 恢复演练命令 | ① 租约过期恢复：向 `jobs` 插入一条 `status='running'`、`lease_until` 已过期、`attempts=1` 的合成任务，观察运行中的 worker 重新领取（≤2.1 秒）并完成；② 死信路径：插入 `kind='moderate_post'` 且 payload 非法（`post_id` 非整数）的任务，观察按 `2^attempts` 退避重试、第 5 次失败后进入 `dead`。两条演练任务均在隔离库内，`dedupe_key` 以 `loadtest-` 开头，不影响压测数据 |

### 修复与本地验证

- 修复：详情页浏览数改异步聚合（`post_view_counters` 缓冲表 + worker 每 10 秒逐帖小事务折叠回 `posts.view_count`）；点赞/取消赞/评论/收藏去掉 `SELECT ... FOR UPDATE`，计数改原子自增且不依赖 `posts.status`。迁移 `c1d2e3f4a5b6`。
- 本地已验（隔离 PostgreSQL 15 + Redis 7 容器、Python 3.11、锁定依赖）：后端全量 pytest **563 passed**；迁移链 `alembic upgrade head` 通过（新迁移在链尾）、`downgrade` → 再 `upgrade` 通过；新增后端用例 `tests/test_hot_post_counters.py` 8 项全绿（含「外部事务锁住热点帖行时详情请求不被阻塞」回归）；`openspec validate --specs` **7/7 通过**；静态守卫 `scripts/check_api_contract.py`、`scripts/check_migrations.py` 通过。
- 负向验证：把详情页改回同步写 `posts.view_count` 后，回归用例在 10 秒内超时失败（详情请求被 `posts` 行锁挡住），恢复后通过。

### 判定

| 场景 | 结果 |
|---|---|
| burst 200req/s × 5 分钟 | 实际 **199.69 req/s**、读 p50/p95/p99 = 9.79ms / **340.16ms** / 383.88ms、写 p50/p95/p99 = 9.16ms / **20.11ms** / 40.10ms、业务成功率 **100.00%**、5xx **0 次**、429 **0 次**、dropped iterations **0** —— **通过**（修复前读 p95 2743.72ms / 写 p95 4063.85ms / dropped 9624 / 实际 167.36 req/s） |
| soak 100req/s × 8 小时 | `2026-11-03T05:56:35Z → 13:56:35Z` **跑满 8 小时整**（2,880,000 次迭代、99.999 req/s）、读 p50/p95/p99 = 9.28ms / **345.78ms** / 402.07ms、写 p50/p95/p99 = 7.89ms / **15.54ms** / 22.11ms、业务成功率 **100.00%**（429 单列后）、5xx **0 次**、429 **49,086 次**（1.70%，单列；全部来自每用户 10 分钟 30 条评论的限流 `RATE_COMMENT = (30, 600)`，压测脚本固定请求类型与账号导致少量账号反复评论；soak 窗口内评论尝试 115,200 次、入库 66,106 条，差额 49,094 与之吻合；限流键是用户维度，不按 IP，与校园 NAT 误伤无关）、dropped iterations **0** —— **通过** |
| steady 100req/s × 30 分钟 | `2026-11-03T19:46:28Z → 20:16:31Z` 在修复后的构建上补跑、实际 **99.98 req/s**（180,001 次迭代）、读 p50/p95/p99 = 9.63ms / **354.72ms** / 403.42ms、写 p50/p95/p99 = 9.36ms / **16.31ms** / 23.40ms、业务成功率 **100.00%**（429 **229 次**单列后）、5xx **0 次**、dropped iterations **0**（2026-11-02 那轮为 16，未达标） —— **通过** |

压测窗口内 PostgreSQL 侧：`log_lock_waits=on` 记录到的行锁等待 **0 次**（`05:56:35Z` 之后无一条 `still waiting for ...`，采样 CSV 的 `lock_not_granted` / `lock_wait_sessions` 全程为 0）；`log_min_duration_statement=500ms` 在长稳窗口内记录 **57 条**慢语句（53 条是帖子列表/详情共用的 `posts JOIN users` 投影，最长 1475.9ms；另 4 条是取证用的全库计数核对 SQL，非线上流量）。**慢语句与行锁无关** —— 逐条 `EXPLAIN (ANALYZE, BUFFERS)` 定位到搜索的 `ILIKE` 全表扫描（74.961ms）与推荐流的热度分排序全表扫描（662.276ms，热度分含 `now()` 无法用表达式索引），已记入 `openspec/specs/optimization/spec.md`（修复前同一根因下慢语句集中在 `UPDATE posts SET view_count=...`）。

长稳期间的其它实测：DB 连接数稳定 35、活跃连接峰值 11；待审任务最旧年龄峰值 **1 秒**、失败 0、死信 **0**；API 进程 RSS 全程 483MB 几乎不变、PostgreSQL 内存进入平台期（**无持续资源增长**）；压测停止后 **6 秒内** CPU 由 73.7% 回落到 0.7%（**恢复耗时 < 1 分钟**）；计数一致性：全库 `like_count` / `comment_count` 不一致帖数均为 **0**；任务恢复演练：租约过期后 **≤2.1 秒**被重新领取并完成，连续失败 5 次后进入死信 `dead`。执行计划（`EXPLAIN (ANALYZE, BUFFERS)`）见 `docs/production/capacity.md`。

**G3 判定**：见 `docs/production/release-gates.md` 的 G3 行（以三个场景全部达标 + 计数/名额一致性与任务恢复报告齐备为准；未达接受条件一律保持未通过）。

### 已知限制

1. **同机发压**：k6、API、PostgreSQL、Redis 跑在同一台 128 vCPU / 295 GB 内存的专用虚拟机上，存在资源竞争；本轮数值仍只能作为**同机基线**，不是生产容量承诺。
2. **补齐场景有限**：本文档列出的补充场景（真实认证→会话刷新、上传→隔离→审核→发帖、重复请求、DB/Redis 超时与断网恢复）本轮未执行；「组局最后名额竞争」与「停 worker 重启（任务恢复）」两项已在隔离环境补跑并留证，数值见 `docs/production/capacity.md`。
3. **第三方边界**：仍只测本地可观测处理能力，未消耗真实审核额度、未验证真实供应商吞吐。
4. **待人工**：专用压测服务器与生产等价拓扑、真实 COS/审核联调、真实成本核算仍需人工安排。推荐流的全表扫描长尾已于 2026-11-03 收敛（搜索改 `pg_trgm` GIN 索引、推荐流改榜单预计算，Alembic 迁移 `d7e8f9a0b123`；隔离环境实测推荐流 109.478ms → 0.893ms、搜索 90.854ms → 0.504ms，burst 读 p95 355.07ms → 23.59ms，数值与代价见 `docs/production/capacity.md`）；剩余的人工决策项是**预计算周期**（本次取 60 秒）与 `pg_trgm` 扩展的引入。


## G3 容量复测（2026-11-03，推荐流纳入压测口径后）

本节记录**把推荐流 `/api/v1/posts`（不带 `order`，学生端默认首屏）纳入 k6 场景配比后**的 burst 复测。`openspec/specs/optimization/spec.md`「帖子列表类查询的全表扫描」条目记录的遗留：推荐流此前从未进入压测流量，容量证据缺这一条。环境与上一节同一专用隔离环境（容器化 PostgreSQL 15 / Redis 7），**未接触生产域名、真实学生数据、开发库或生产 Redis**；本轮**只改压测脚本与文档，未改后端代码**。

### 环境与命令

| 项 | 值 |
|---|---|
| 代码版本 | 分支 `agent/add-feed-load-scenario-03a2d6476442`（PR #38），应用镜像 `schoolwall-loadtest:local` 与 PR #36 合并后的代码一致 |
| 宿主 / 工具 | KVM 虚拟机 / Ubuntu 24.04.5；k6 v0.57.0；脚本 = 本工单工作树的 `scripts/load/campus.js` |
| 数据库 / 缓存 | PostgreSQL 15.14（容器 `swload-pg`，端口 55433，专用库 `schoolwall_loadtest`）/ Redis 7.4.7（容器 `swload-redis`，端口 6399，逻辑库 13） |
| 数据集 | **同一隔离实例**：10000 用户 / 100000 帖（95000 可见 + 5000 待审）/ 580121 评论（种子 50 万 + 历轮压测评论累积，未重建库）；`post_hot_scores` 95000 行 |
| 口径变化 | 既有七项场景权重与相对比例不变（45/25/10/7/6/4/3），只新增推荐流权重 10，循环长度 100→110 ⇒ 推荐流有效占比 9.1%；脚本新增按场景分列的 `scenario_<name>_count` / `scenario_<name>_duration` |
| 发压命令 | `ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION ALLOWED_LOAD_HOST=127.0.0.1 BASE_URL=http://127.0.0.1:8000 PROFILE=burst RATE=200 DURATION=5m k6 run scripts/load/campus.js` |
| 执行计划取证 | 捕获应用真实执行的语句后 `EXPLAIN (ANALYZE, BUFFERS)`（隔离容器内 Python 3.11 + 仓库锁定依赖） |

### 判定

| 项 | 结果 |
|---|---|
| burst 200req/s × 5 分钟 | `2026-11-03T21:30:50Z → 21:35:54Z`，实际 **199.893 req/s**（60000 次迭代）、读 p50/p95/p99 = 9.83ms / **23.26ms** / 33.58ms、写 p50/p95/p99 = 8.84ms / **18.37ms** / 31.62ms、业务成功率 **99.887%**（429 **68 次**单列后）、5xx **0 次**、dropped iterations **0** —— **通过** |
| 推荐流路径实测延迟 | p50 **11.45ms** / p95 **18.19ms** / p99 27.75ms / 最大 151.77ms（5450 次请求，占 9.08%） |
| 推荐流执行计划 | `Index Only Scan Backward using ix_post_hot_scores_rank on post_hot_scores` → `Index Scan using posts_pkey` → `Memoize` → `Index Scan using users_pkey`，**Execution Time 0.860ms**，**无全表 Seq Scan、单次 < 50ms**（收敛前为 Parallel Seq Scan → Sort，109.478ms / 662.276ms） |
| 压测窗口内数据库证据 | 行锁等待（`log_lock_waits`）**0 次**；>500ms 慢语句 **5 条，全部是 worker 每约 63 秒一次的榜单刷新**（2742.062 / 2729.218 / 2692.669 / 2759.936 / 2725.793 ms），**无一条是用户请求路径** |

**G3 判定**：G3 仍为通过，容量证据新增「推荐流在压测流量内」这一条；数值与判定见 `docs/production/capacity.md` 与 `docs/production/release-gates.md` 的 G3 行。

### 本地已验与仍待 CI 判定

- 本地已验：`python3 -m unittest discover -s scripts/tests`（新增 `scripts/tests/test_load_campus_mix.py` 5 项全绿；`test_proxy_headers` 因本机无 uvicorn 无法导入，其余 49 项全绿，与上一轮相同）；k6 脚本语法检查（`node --check`）通过。
- **后端用例套件、迁移链与 API 契约由 Production CI 判定**（本机无 PostgreSQL/Redis）；本工单未改后端代码与迁移，接口面不变。
- `openspec validate --specs` 由 Production CI 判定（本机未安装 openspec CLI）；本工单只改了 `openspec/specs/optimization/spec.md` 里与推荐流压测口径、G3 状态相关的**记录性文字**，未增删需求条目、未改任何 requirement。


## G2 可靠性：隔离环境备份 / 恢复 / 应用回滚演练（2026-11-03，专用隔离环境）

本节是**发布门禁 G2 的第一次真实演练取证**。环境为仓库外的专用隔离目录（专用 KVM 虚拟机 + 容器化 PostgreSQL 15.14 / Redis 7.4.7，即 k6 压测所用的同一套实例），**未接触生产域名、生产实例、开发库、生产 Redis 或真实学生数据**；演练数据全部是合成的压测数据集。

演练范围：**逻辑备份 → 新建隔离恢复库恢复 → 恢复后一致性校验 → 应用回滚**。**不包含**异机备份、备份加密、WAL 归档 / PITR、告警送达与人工确认、以不可变 digest 制品走真实发布窗口（这些需要真实基础设施与人工安排，见本节末「剩余缺口」）。

隔离守卫：恢复目标库 `schoolwall_restore_migration` 在恢复前**不存在**（脚本查到已存在即拒绝执行），库名带隔离后缀 `_migration`；仓库自带的 `scripts/check_restore.py` 另需 `ENVIRONMENT=test` + 显式 `MIGRATION_TEST_ACK=YES_ISOLATED_DATABASE`；**全程没有对任何已有数据的库做过写入或删除**。

### 环境

| 项 | 值 |
|---|---|
| 宿主 | 专用 KVM 虚拟机 / Ubuntu 24.04.5（与 2026-11-03 G3 容量复测同一台） |
| 数据库 | PostgreSQL 15.14 容器 `swload-pg`（宿主端口 55433，专用库 `schoolwall_loadtest`） |
| 缓存 | Redis 7.4.7 容器 `swload-redis`（宿主端口 6399，逻辑库 13） |
| 数据集 | 合成压测数据：10000 用户 / 100000 帖 / 582233 评论 / 167760 足迹 / 82240 任务 / 95000 榜单行；`alembic_version = d7e8f9a0b123` |
| 演练脚本位置 | 仓库外隔离目录 `/home/kikun/loadenv2/drill`（不进仓库）；下文给出命令原文，可原样复现 |

### 1）逻辑备份（与 `deploy/backup.sh` 同形）

`deploy/backup.sh` 本身走 `docker compose ... exec db`（面向生产 compose 项目托管的 db），隔离实例不是 compose 托管，因此按**同一形态**用等价命令执行：同样的 `umask 077` → `.partial` → `gzip --test` → `mv` → `deploy/backup_retention.py` → sha256 步骤，未改脚本本身。

```bash
docker exec swload-pg pg_dump -h 127.0.0.1 -p 55433 -U loaduser -d schoolwall_loadtest \
  | gzip > backups/ey_wall_2026-11-03_220306.sql.gz.partial
gzip --test backups/ey_wall_2026-11-03_220306.sql.gz.partial
mv -- backups/ey_wall_2026-11-03_220306.sql.gz.partial backups/ey_wall_2026-11-03_220306.sql.gz
python3 deploy/backup_retention.py backups 14
sha256sum backups/ey_wall_2026-11-03_220306.sql.gz
```

| 项 | 实测值 |
|---|---|
| 备份耗时 | **4.536 秒**（`2026-11-03T22:03:06Z` 起，`pg_dump | gzip` 本体耗时；含 `gzip --test`、保留策略与 sha256 的整段在 `22:03:12Z` 结束） |
| 备份文件 | `ey_wall_2026-11-03_220306.sql.gz`，**43,929,696 字节**（41.9 MiB） |
| 完整性校验 | `gzip --test` **通过** |
| sha256 | `5c94f0004bca36e008bc064f5a1168b8559ea092efb711cc8c4859a5dd1ea29d` |

### 2）恢复到新建的隔离恢复库

```bash
# 守卫：目标库必须不存在，且库名带隔离后缀
docker exec swload-pg psql -h 127.0.0.1 -p 55433 -U loaduser -d postgres \
  -qtAc "SELECT 1 FROM pg_database WHERE datname='schoolwall_restore_migration'"   # 空 → 可创建
docker exec swload-pg psql -h 127.0.0.1 -p 55433 -U loaduser -d postgres \
  -qc 'CREATE DATABASE "schoolwall_restore_migration" OWNER loaduser'
gunzip -c backups/ey_wall_2026-11-03_220306.sql.gz \
  | docker exec -i swload-pg psql -h 127.0.0.1 -p 55433 -U loaduser -d schoolwall_restore_migration \
      -v ON_ERROR_STOP=1 -q
```

**恢复耗时（RTO 的数据恢复段）= 8.145 秒**（`2026-11-03T22:03:14Z` → `22:03:22Z`，`ON_ERROR_STOP=1`，无错误输出）。

### 3）恢复后数据一致性

逐表比对源库 `schoolwall_loadtest` 与恢复库 `schoolwall_restore_migration` 的**行数**与**内容校验和**（`md5(每行文本)` 排序后再聚合）：

| 表 | 源库行数 | 恢复库行数 | 行数一致 | 内容 md5 一致 |
|---|---|---|---|---|
| users | 10000 | 10000 | 是 | 是 |
| posts | 100000 | 100000 | 是 | 是 |
| comments | 582233 | 582233 | 是 | 是 |
| footprints | 167760 | 167760 | 是 | 是 |
| jobs | 82240 | 82240 | 是 | 是 |
| moderation_records | 164467 | 164467 | 是 | 是 |
| notifications | 85553 | 85553 | 是 | 是 |
| likes | 20788 | 20788 | 是 | 是 |
| user_sessions | 30000 | 30000 | 是 | 是 |
| parties / party_members | 4 / 6 | 4 / 6 | 是 | 是 |
| post_view_counters | 1000 | 1000 | 是 | 是 |
| sensitive_words | 20 | 20 | 是 | 是 |
| alembic_version | `d7e8f9a0b123` | `d7e8f9a0b123` | 是 | 是 |
| post_hot_scores | 95000 | 95000 | 是 | **否** |
| post_hot_score_state | 1 | 1 | 是 | **否** |
| restore_drill_marks（RPO 标记表） | 8 | 2 | **否** | **否** |

- 共 38 张表：除 `post_hot_scores` / `post_hot_score_state`（演练期间 worker 刷新榜单）与 `restore_drill_marks`（RPO 标记表）外，**逐表行数与内容校验和完全相同**。
- `post_hot_scores` / `post_hot_score_state` 行数相同但内容不同：演练期间后台 worker 每约 60 秒重算一次推荐流榜单，源库在快照之后又刷新过一次 —— 这是**应用继续写入**造成的差异，不是恢复丢失。
- `restore_drill_marks` 的差异是**演练刻意制造的写入缺口**，即下面的 RPO 取证对象。

仓库自带的 `scripts/check_restore.py`（带隔离库守卫）再在**恢复库**上跑一次：

```bash
ENVIRONMENT=test MIGRATION_TEST_ACK=YES_ISOLATED_DATABASE \
DATABASE_URL=postgresql://loaduser:loadpass@127.0.0.1:55433/schoolwall_restore_migration \
PG_BIN_DIR=<指向隔离实例 pg_dump/pg_restore 的包装目录> \
python3 scripts/check_restore.py
# → Synthetic logical restore matched rows, identities and schema version:
#   {'users': 10000, 'login_identities': 0, 'posts': 100000, 'footprints': 167760,
#    'jobs': 82240, 'student_verifications': 0}
# → Logical restore smoke PASS; this is not off-host PITR/RPO/RTO evidence
```

耗时 13.988 秒，退出码 0。

### 4）RPO 实测（恢复点相对最后一次写入的丢失窗口）

方法：演练期间以**固定 1 次/秒**的节拍向隔离库写入合成标记行（表 `restore_drill_marks`，`marker_at` 取 `clock_timestamp()` 的真实写入时刻），**备份与写入并发进行**；RPO = 恢复点（恢复库里最后一条被快照包含的标记）与最后一次写入（源库最后一条标记）之间的丢失窗口。

| 项 | 实测值 |
|---|---|
| 源库最后写入 | `2026-11-03T22:03:12.303848+00:00`（累计 8 行） |
| 恢复点（恢复库内最后一条标记） | `2026-11-03T22:03:05.846472+00:00`（恢复库内 2 行） |
| **RPO 实测** | **6.457 秒** |
| 丢失的标记写入 | **6 行**（1 秒节拍） |

口径说明：这是**纯逻辑备份（无 WAL 归档）**下的丢失窗口，量级 ≈ 备份耗时（4.536 秒）+ 写入间隔（1 秒）+ 取整误差。**它不是 PITR 口径的 RPO**：开启 WAL 归档（`archive_timeout`）后 RPO 必须另测。

### 5）应用回滚演练（`scripts/rollback-release.sh`）

隔离发布根目录 `/home/kikun/loadenv2/release-root`，结构与仓库发布约定一致：`releases/<revision>/{deploy/docker-compose.prod.yml, release.env}`、`shared/.env`、`current` / `previous` 符号链接。

两份制品都用仓库的 `backend/Dockerfile` 构建：**本次制品 = `703ed0f`（本工单 HEAD）**，**上一版制品 = `7e4b490`（PR #32 的后端代码）**。隔离环境访问不到 Docker Hub，构建时去掉了 `# syntax=docker/dockerfile:1` 一行（取不到 dockerfile 前端镜像）并把 pip 源指向镜像站，**其余内容逐行未改**（CI 仍用仓库原文件）。两份制品确实不同：上一版镜像内 `grep -rl post_hot_scores /app/app` 无命中，本次镜像命中 `app/models/hot_score.py`、`app/services/post.py`、`app/services/hot_scores.py` 三个文件。

部署本次制品（等价于 `scripts/rollout.sh` 的 compose 步骤；`rollout.sh` 本身要求 manifest 里的 `ghcr.io` 不可变 digest 与 `shared/release-gates.json` 的 `production_approved` 审批，隔离环境两者都拿不到，故按同一 compose 契约手工执行）：

```bash
docker compose --project-name schoolwall --env-file shared/.env \
  --env-file releases/$REVB/release.env -f releases/$REVB/deploy/docker-compose.prod.yml up -d db redis
docker compose ... --profile tools run --rm migrate
docker compose ... up -d --no-build backend worker
```

部署后健康检查：`/health/live` 与 `/health/ready` 均返回 `revision = 703ed0f34ee1b96688c4593ca84b67bb1df3f765`（= 本次制品），`alembic_version = d7e8f9a0b123`。

回滚（**仓库自带脚本**，只回退应用、不动数据）：

```bash
bash scripts/rollback-release.sh /home/kikun/loadenv2/release-root \
  /home/kikun/loadenv2/release-root/releases/7e4b490b88df87a86e1ffb523b0ee932ad9ae312
# → application rollback ready; database schema retained
```

| 项 | 实测值 |
|---|---|
| **回滚耗时** | **3.650 秒** |
| 回滚后 `/health/live` | `{"status":"ok","revision":"7e4b490b88df87a86e1ffb523b0ee932ad9ae312"}`（= 上一版制品） |
| 回滚后 `/health/ready` | `{"status":"ok","revision":"7e4b490b88df87a86e1ffb523b0ee932ad9ae312"}` |
| backend / worker 镜像 | 切回上一版制品镜像 |
| 数据库 schema | **仍为 `d7e8f9a0b123`（未降级）** |
| `current` 符号链接 | 切到上一版 release 目录 |

诚实备注：脚本的健康轮询里第一次 `curl` 出现过一次 `curl: (56) Recv failure: Connection reset by peer`（容器刚重建、端口尚未就绪），脚本按既有设计重试后通过；**未对脚本做任何修改**。

回滚后的上一版制品在**恢复出来的隔离库**上继续正常服务数据：单独起上一版镜像指向 `schoolwall_restore_migration`，`/health/live`、`/health/ready` 均 ok，`GET /api/v1/posts` 返回 **HTTP 200**、20 条，恢复库核心行数不变（users=10000 / posts=100000 / comments=582233，`schema=d7e8f9a0b123`）。

### 汇总数值

| 项 | 实测值 | 口径与限制 |
|---|---|---|
| 逻辑备份耗时 | **4.536 秒** | 同一台隔离宿主，10000 用户 / 10 万帖 / 58.2 万评论合成数据集，pg_dump + gzip |
| 备份文件 | 43,929,696 字节，sha256 `5c94f000…` | `gzip --test` 通过 |
| 恢复耗时（RTO 数据恢复段） | **8.145 秒** | 新建隔离恢复库，`ON_ERROR_STOP=1` |
| 恢复后一致性 | 38 张表逐表行数 + 内容 md5 一致（2 张被应用并发写入的榜单表与 1 张 RPO 标记表除外） | 另经 `scripts/check_restore.py` PASS |
| **RPO（恢复点相对最后一次写入的丢失窗口）** | **6.457 秒**（1 秒节拍的标记写入丢了 6 条） | **纯逻辑备份、无 WAL 归档口径，不是 PITR 承诺** |
| **应用回滚耗时** | **3.650 秒** | 仓库脚本 `scripts/rollback-release.sh`，含 revision + readiness 双重健康门禁 |
| 回滚后状态 | revision 切回上一版制品、schema 保留未降级、上一版制品在恢复库上正常服务数据 | |

### 剩余缺口（未取得 → 门禁与任务行保持未通过 / 未勾选）

1. **异机备份**：备份文件仍落在演练宿主的本地目录，未复制到第二台机器或对象存储，也未验证异机恢复。
2. **加密**：备份未加密；`deploy/backup/` 只有 pgBackRest 配置样例与手册，没有实际启用加密（需人工在真实环境配置密钥）。
3. **WAL 归档 / PITR**：本演练没有 `archive_timeout` 与归档链路，**RPO 实测值只代表逻辑备份口径**；目标 RPO≤1 小时、RTO≤4 小时必须在开启 WAL 归档的真实环境重测。
4. **告警真实到达并被确认**：未演练（无真实告警通道，也没有值班人确认记录）。
5. **真实发布窗口**：演练用的是本地构建的镜像标签，**不是 `ghcr.io` 的不可变 digest 制品**；`scripts/rollout.sh`（要求 manifest 里的 ghcr digest + `shared/release-gates.json` 的 `production_approved` 审批）与 GitHub production environment 的 required reviewers 都没走到。因此 `openspec/changes/production-multiplatform/tasks.md` 第 29 行「真实发布/回滚/完整恢复，证明RPO/RTO」**保持未勾选**。
6. **相同制品预发布**：本次是同一份代码在隔离环境「部署 → 回滚」，未做「相同 digest 制品在预发布与生产各跑一遍并比对」的比对。
7. **第 24 行「目标环境杀worker、审核中断、Redis/DB故障演练」**：本工单未执行（G3 容量演练已留证 worker 租约过期重新领取与死信路径，但杀 worker、审核中断、Redis/DB 故障演练未做），**保持未勾选**。**该行已于 2026-11-03 的故障注入演练中取得隔离环境证据，见下一节「G2 可靠性：隔离环境故障注入演练」；但演练环境仍是隔离环境而非目标环境，真实告警送达与人工确认仍属人工安排，故该行按既有口径保持未勾选。**

本工单未改后端代码、迁移与 API 契约；后端全量用例、迁移链与 API 契约由 **Production CI** 判定。


## G2 可靠性：隔离环境故障注入演练（2026-11-03，专用隔离环境）

本节是**发布门禁 G2「故障恢复」项的故障注入取证**。环境为仓库外的专用隔离目录（容器化 PostgreSQL 15.14 / Redis 7.4.7，即 k6 压测所用的同一套实例），**未接触生产域名、生产实例、开发库、生产 Redis 或真实学生数据**；演练数据全部是合成的。

演练范围：**杀后台 worker → 任务租约过期后被重新领取 → 连续失败 5 次进入死信 dead**、**审核供应商中断（超时/失败）→ 内容保持待审、旧决定不被覆盖、重试按退避生效**、**Redis 与 PostgreSQL 故障 → `/health/ready` 返回 503、写入不产生半成品数据、恢复后自动回到可用**。**不包含**真实告警送达与人工确认、真实目标环境演练、审核供应商真实额度/费用验证（这些需要真实基础设施与人工安排，见本节末「剩余缺口」）。

隔离守卫：演练数据落在**独立库 `schoolwall_drill_loadtest`**（库名带 `_loadtest` 后缀，仓库自带 `scripts/load/seed.py` 的 `validate_target` 只允许向 `*_loadtest` 库播种）与**独立 Redis 逻辑库 15**；k6 压测用的 `schoolwall_loadtest` 库与 Redis 逻辑库 13 **全程未被写入**。演练脚本在仓库外隔离目录 `/home/kikun/loadenv2/drill/failure`，不进仓库。

### 环境

| 项 | 值 |
|---|---|
| 数据库 | PostgreSQL 15.14 容器 `swload-pg`（宿主端口 55433），演练库 `schoolwall_drill_loadtest` |
| 缓存 | Redis 7.4.7 容器 `swload-redis`（宿主端口 6399），演练逻辑库 15 |
| 演练应用 | 独立容器 `drill-api`（`127.0.0.1:8011`，2 个 uvicorn worker）与 `drill-worker`（`python -m app.worker`），与 k6 压测容器 `swload-api`/`swload-worker` 并存但库与 Redis 逻辑库互不重叠 |
| 镜像 | `schoolwall-loadtest:local`（由仓库 `backend/Dockerfile` 构建，代码与本工单 HEAD 的 `backend/` 逐文件一致，已用 `diff -rq` 核对） |
| 数据集 | 合成数据：20 用户 / 100 帖（`scripts/load/seed.py`，带 `ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE` 守卫） |
| 审核供应商隔离 | 演练容器注入一对**占位用的假审核凭证**（`TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY`，值只存在于隔离目录的环境变量里，不入库不入日志），并用 `--add-host` 把 `tms.tencentcloudapi.com` 与 `ims.tencentcloudapi.com` 指向 RFC5737 黑洞地址 `192.0.2.1` —— **任何审核调用都不出网、不触达真实供应商**，只会在本机超时失败 |
| 演练脚本位置 | 仓库外隔离目录 `/home/kikun/loadenv2/drill/failure`（不进仓库）；下文给出命令原文，可原样复现 |

### 1）杀后台 worker → 租约过期后被重新领取 → 连续失败 5 次进入死信 `dead`

方法：先停掉 worker 让审核任务停在 `pending`，再启动 worker 并**在任务被领取的瞬间 `SIGKILL` 容器**（`docker kill --signal=KILL`，容器退出码 **137**），随后重启 worker，观察租约（`LEASE_SECONDS = 180`）过期后任务被重新领取。

| 项 | 实测值 |
|---|---|
| 任务被领取时刻 | `2026-11-03T23:11:25Z`（`attempts=1`，`lease_until=2026-11-03 23:14:25.515029+00`） |
| worker 被强杀时刻 | `2026-11-03T23:11:25Z`（`docker kill --signal=KILL drill-worker`，容器 `Exited (137)`） |
| 杀 worker 后任务状态 | 仍为 `running` / `attempts=1`，**租约未过期，任务不丢**（`db_now=2026-11-03 23:11:25.871271`） |
| worker 恢复时刻 | `2026-11-03T23:11:25Z`（`docker start drill-worker`） |
| **租约过期后被重新领取时刻** | `2026-11-03T23:14:26.141Z`，`attempts` **1 → 2**，新 `lease_until=23:17:25.962934+00` |
| **租约重新领取耗时** | **0.626 秒**（租约到期 `23:14:25.515029Z` → 重新领取 `23:14:26.141Z`；worker 主循环每轮空闲等待 1 秒，领取在下一轮即发生） |
| 连续失败后进入死信 | `attempts` 依次 1→2→3→4→**5**，`status=dead`，`last_error=ModerationRetry`（`2026-11-03T23:09:39Z` 那条任务与 `23:17:22Z` 那条任务同样走到 `dead`） |
| 死信条数（演练结束） | `jobs` 表 `status=dead` 共 **4 条**（均为审核供应商不可达导致的 `ModerationRetry`，`attempts=5/5`） |

退避实测（同一任务的相邻两次失败间隔，`available_at - 上次失败时刻`）：**2 秒 → 4 秒 → 8 秒 → 16 秒**，与 `services/jobs.py` 的 `2 ** attempts`（上限 300 秒）一致。

演练期间内容**始终保持待审**：被强杀与被重试的帖子 `posts.status` 全程为 **0**，从未被误放行为公开内容。

### 2）审核中断（供应商超时/失败）→ 内容保持待审、旧决定不被覆盖、重试按退避生效

方法：审核供应商在演练容器内被指向黑洞地址（见上表），因此每次审核调用都会**超时约 15 秒**后失败（容器内实测 `provider error: ModerationProviderError after 15.09 s`，`check_text` 返回 `verdict=error reason=provider_unavailable`）。容器环境确认 `MODERATION_FAIL_OPEN=false`。

| 项 | 实测值 |
|---|---|
| 单次审核调用失败耗时 | **15.09 秒**（SDK `reqTimeout=15` 到点抛 `ModerationProviderError`） |
| 任务重试轨迹 | `attempts` 0→1→2→3→4→**5**，`last_error=ModerationRetry`，`2026-11-03T23:17:22.643Z` 进入 `dead` |
| **退避间隔实测** | **2 秒 → 4 秒 → 8 秒 → 16 秒**（`available_at` 依次 `23:15:40.209208` → `23:16:13.287780` → `23:16:36.330334` → `23:17:07.396351`） |
| **内容保持待审** | 供应商全程不可达的帖子 `posts.status` 始终为 **0**；`visible_in_public_feed`（`status=1` 才公开）计数为 **0** —— 故障期间内容**不公开** |
| 审核记录不写脏数据 | `moderation_records` 表在供应商连续失败的整个窗口内**新增 0 行**（失败路径只落 `jobs.last_error`，不写审核判定） |
| 旧决定不被覆盖（人工先决定） | 隔离演练账号经**真实管理台接口** `PUT /api/v1/admin/posts/{id}/status?status=1` 把待审帖（`post_id=106`）过审为 `status=1`（此时该帖的机器审核记录数为 **0**）；随后恢复 worker，它领取该帖的任务并按本地硬敏感词给出 `reject` 判定 —— **帖子 `status` 仍为 1**（`updated_at` 未变），`moderation_records` 里**没有补写与人工决定冲突的判定行**，任务记为 `succeeded`。**RESULT: PASS** |
| 人工决定留痕 | 管理台审计日志 `GET /api/v1/admin/logs` 记录 `action=post.status target_type=post target_id=106 detail={'new_status': 1}` |
| 旧决定不被覆盖（机器先决定后人工改判） | 已过审帖（`post_id=2`）被补投一个审核任务，worker 处理后帖子 `status` 仍为 **1**，任务 `succeeded` |

### 3）Redis 与 PostgreSQL 故障 → `/health/ready` 返回 503、写入不产生半成品数据、恢复后自动回到可用

方法：直接停止与 k6 压测同一套专用实例的容器（`docker stop swload-redis` / `docker stop swload-pg`），观察就绪探针与写路径，再启动容器观察自动恢复。

| 项 | Redis 故障 | PostgreSQL 故障 |
|---|---|---|
| 故障注入时刻 | `2026-11-03T23:18:25Z` | `2026-11-03T23:18:28Z` |
| **`/health/ready` 状态码** | **503**（耗时 0.013633 秒，body `{"status":"unavailable","revision":"development"}`） | **503**（耗时 0.005658 秒，body 同上） |
| `/health/live` 状态码 | **200**（存活探针与就绪探针分离正确） | **200** |
| 故障期间写路径 | **HTTP 503**，body `{"code":503,"message":"安全校验服务暂时不可用，请稍后重试",...}`（Redis 限流依赖不可达，命中 `redis_error` 处理器） | **HTTP 500**，body `{"code":500,"message":"服务暂时不可用",...}` |
| **故障期间是否出现半成品数据** | **否**：`posts/jobs/comments/media_assets/moderation_records` 计数 `103\|4\|0\|0\|0` 与故障前**逐项一致** | **否**：写路径在连接层就失败，未落任何行；恢复后计数 `104\|5\|0\|0\|0`，增量恰为恢复后正常写入的 1 帖 + 1 任务 |
| 恢复时刻 | `2026-11-03T23:18:28Z`（`docker start swload-redis`） | `2026-11-03T23:18:32Z`（`docker start swload-pg`） |
| **恢复时间（故障注入 → 就绪恢复 200）** | **3.88 秒** | **4.45 秒** |
| worker 侧表现 | — | 容器日志连续记录 `ERROR:__main__:worker iteration failed error=ConnectionRefusedError` —— **任务不丢、不误判成功**，恢复后继续处理 |

**诚实记录的观察到的异常**：PostgreSQL 完全不可达时，写路径返回的是 **500**（`{"code":500,"message":"服务暂时不可用"}`，API 日志 `event=unhandled_error`）而不是与 Redis 故障一致的 **503**。根因已定位：连接被拒时抛出的 `ConnectionRefusedError` 是 `OSError` 子类，**不是 `SQLAlchemyError`**，因此 `app/main.py` 的 `database_error` 处理器（返回 503「数据服务暂时不可用」）没有接住它，最终落到兜底的 `unhandled_error` 500 分支。就绪探针不受影响（`/health/ready` 仍正确返回 503），写入也仍未产生半成品数据，因此**不构成数据正确性问题**，但**错误码语义不一致（依赖不可用报 500 而非 503）**，且 500 会被计入 5xx 错误预算。该项属**新发现的代码缺陷**，按仓库既有约定不擅自改动生产代码，已如实记录在此并留待人工决定是否修复（见下方「剩余缺口」第 8 条）。演练期间未修改任何后端代码。

> **2026-11-04 更新**：该缺陷已按 `openspec/specs/optimization/spec.md` 同名条目修复（`backend/app/main.py` 补 `OSError` 处理器，连接层异常统一返回 503），并在**同一套隔离环境**做过修复前 / 修复后对照复测，实测数值见下一节「G2 可靠性：PostgreSQL 不可达时写路径错误码修复复测（2026-11-04）」。

### 汇总数值

| 项 | 实测值 | 口径与限制 |
|---|---|---|
| 杀 worker 后租约重新领取耗时 | **0.626 秒** | 租约 `LEASE_SECONDS=180` 到期后由恢复的 worker 在下一轮主循环领取，`attempts` 1→2 |
| 连续失败进入死信 | **5 次**（`attempts=5/5`，`status=dead`，`last_error=ModerationRetry`） | 死信条数（演练结束）4 条，全部为审核供应商不可达所致 |
| 重试退避间隔 | **2 / 4 / 8 / 16 秒** | 与 `2 ** attempts`（上限 300 秒）一致，两次独立观测一致 |
| 审核供应商单次调用失败耗时 | **15.09 秒** | SDK `reqTimeout=15`；供应商为演练黑洞地址，未触达真实供应商 |
| 供应商故障期间内容可见性 | **不公开**（`posts.status` 全程 0，公开信息流计数 0） | `MODERATION_FAIL_OPEN=false` |
| 旧决定被覆盖 | **未发生**（人工先决定 → 机器重试后 `status` 仍为 1；机器先决定 → 人工改判后机器不改写） | 走真实管理台接口 + 真实 worker |
| Redis 故障 `/health/ready` | **503**（0.013633 秒），`/health/live` **200** | 写路径 **503** |
| PostgreSQL 故障 `/health/ready` | **503**（0.005658 秒），`/health/live` **200** | 写路径 **500**（观察到的异常，见上文诚实记录） |
| 故障期间半成品数据 | **0**（两张表的计数逐项比对一致） | |
| Redis 恢复时间 | **3.88 秒** | 故障注入 → `/health/ready` 回到 200 |
| PostgreSQL 恢复时间 | **4.45 秒** | 故障注入 → `/health/ready` 回到 200 |

### 剩余缺口（未取得 → 门禁与任务行保持未通过 / 未勾选）

1. **真实告警送达并被确认**：未演练（隔离环境没有真实告警通道，也没有值班人确认记录）。
2. **目标环境演练**：本次是隔离环境（专用容器化实例 + 合成数据），**不是生产目标环境**；生产实例的 worker 进程管理方式、审核供应商真实额度/费用、真实网络分区表现仍需在目标环境复测。因此 `openspec/changes/production-multiplatform/tasks.md` 第 24 行「目标环境杀worker、审核中断、Redis/DB故障演练」**按既有口径保持未勾选**，只在备注中记录本节隔离环境已取得的证据与剩余缺口。
3. **审核供应商真实调用未触达**：演练用的是黑洞地址 + 假凭证，**真实腾讯云审核接口的响应形态、额度扣减、费用与真实 SLA 未验证**（需人工提供真实凭证与额度）。
4. **PostgreSQL 不可达时写路径返回 500 而非 503**：本节 3）诚实记录的新发现缺陷，**已于 2026-11-04 修复并复测**（写路径由 500 变为 503，见下一节）；本条不再是缺口。
5. **异机备份、备份加密、WAL 归档 / PITR、真实发布窗口、相同制品预发布比对**：见上一节「G2 可靠性：隔离环境备份 / 恢复 / 应用回滚演练」的剩余缺口，同样未取得。

本工单未改后端代码、迁移与 API 契约；后端全量用例、迁移链与 API 契约由 **Production CI** 判定。


## G2 可靠性：PostgreSQL 不可达时写路径错误码修复复测（2026-11-04，专用隔离环境）

本节是上一节 3）记录的「PostgreSQL 完全不可达时写路径返回 500 而非 503」缺陷的**修复后复测**。

修复内容（`backend/app/main.py`）：数据库连接被拒时 SQLAlchemy 抛出的 `ConnectionRefusedError` 是 `OSError` 子类、**不是 `SQLAlchemyError`**，原来的 `database_error` 处理器接不住，异常一路落到 `request_context` 中间件的兜底 `unhandled_error` 500 分支。现在新增 `OSError` 处理器：**连接层异常**（`ConnectionError` / `TimeoutError` / `socket.gaierror`，覆盖 `ConnectionRefusedError`）统一返回 **503「数据服务暂时不可用，请稍后重试」**，与依赖不可用的语义一致；**与依赖无关的 `OSError`**（文件读写失败等）仍按内部错误 500 处理，不改写既有语义。**接口契约与业务语义未变，只改错误码与文案。**

复测方法：同一套专用隔离环境（容器化 PostgreSQL 15.14 / Redis 7.4.7）、**同一套合成数据与同一套账号**，同时启动两份 API ——「修复前」= 本工单修复前的 `backend/app/main.py`，「修复后」= 含本次修复的同一文件；停**同一个** PostgreSQL 容器后同时打两侧写路径，直接对照状态码与响应体。演练数据仍落在**独立库 `schoolwall_drill_loadtest`** 与**独立 Redis 逻辑库 15**，k6 压测用的 `schoolwall_loadtest` 库与逻辑库 13 全程未被写入；演练脚本在仓库外隔离目录 `/home/kikun/loadenv2/drill/failure`（不进仓库）。

| 项 | 修复前 | 修复后 |
|---|---|---|
| 故障注入 | `docker stop swload-pg`（`2026-11-04T00:00:45Z`） | 同一个容器、同一时刻 |
| **写路径状态码**（`POST /api/v1/posts`） | **500** | **503** |
| **写路径响应体** | `{"code":500,"message":"服务暂时不可用","data":null,...}` | `{"code":503,"message":"数据服务暂时不可用，请稍后重试","data":null,"detail":"数据服务暂时不可用，请稍后重试","request_id":...}` |
| `/health/ready`（故障期间） | 503（body `{"status":"unavailable",...}`） | **503**（耗时 0.003468 秒，body 同上） |
| `/health/live`（故障期间） | 200 | **200** |
| 恢复 | `docker start swload-pg`（`2026-11-04T00:00:48Z`） | 同一容器、同一时刻 |
| **恢复时间（故障注入 → `/health/ready` 回到 200）** | — | **5.32 秒** |
| 恢复后写入 | — | **HTTP 200**，body `{"code":0,"message":"发布成功，图片审核中","data":{"post_id":101,"status":0}}` |
| **故障期间是否出现半成品数据** | 否 | **否**：故障期间 PostgreSQL 已停无法读计数，改在恢复后比对基线 —— 基线 `posts/jobs/comments/media_assets/moderation_records = 100/0/0/0/0`，恢复后 `101/1/0/0/0`，**增量恰为恢复后那 1 帖 + 1 任务**（`posts.id=101` 的 `moderate_post` 任务数 = 1）；故障期间打出的两次写请求（修复前 / 修复后各一次）**未留下任何行** |
| 半成品检查（恢复后） | — | 「待审帖无任务」只命中**合成种子自带的 5 条待审帖**（`id` 1/21/41/61/81，基线即存在，与演练写入无关）；「任务无帖子」**0 行** |

### 本地已验与仍待 CI 判定

| 项 | 结果 |
|---|---|
| 后端新增用例 | `backend/tests/test_db_unavailable.py`（3 项）：写路径数据库连接失败返回 **503**、就绪探针 503 / 存活探针 200、与依赖无关的 `OSError` 仍为 500 |
| 后端全量 pytest | **本地在隔离环境（容器化 PostgreSQL 15.14 / Redis 7.4.7，测试库 `schoolwall_test`、Redis 逻辑库 13）实跑：578 passed / 0 failed（128.73 秒）**。本机不跑生产数据库，**Production CI 仍是后端套件、迁移链与 API 契约的权威判定** |
| 迁移链 | 本次**无新增迁移**，接口面未变；`scripts/check_migrations.py` 与 `scripts/check_api_contract.py` 由 CI 复跑 |
| 未改动 | 未改发布门禁口径、未改接口契约、未改业务语义、未接触生产域名 / 生产实例 / 真实学生数据 |


## 已知发布阻断

主前端官方npm audit：**0 high / 0 critical**（20 moderate 告警包：17 条继承自 `@intlify/core-base` 的构建期advisory 链、3 条来自 `openapi-typescript` → `@redocly/openapi-core` → `minimatch` 链，均为 devDependency 传递依赖，产物中不含该包）；管理台官方npm audit：**0 vulnerabilities**（2026-11-01，`vue-tsc` 升至 `~3.1.8` 后 `minimatch` 依赖链消失）。旧基线里的 braces3.0.3 告警（GHSA-vfj7-8cjw-p6xm）已由**上游撤回该 advisory**，npm 不再下发，braces 本身仍是最新版3.0.3、未发生版本变更；同期新披露的 vue-i18n/@intlify、body-parser、follow-redirects 高危已通过移除未使用的 vue-i18n、回调 @intlify overrides 至9.1.9/9.14.4、overrides body-parser→^1.20.9 与 follow-redirects→^1.16.2 全部清除。详细依赖链、原始报告与解除条件见[客户端验收记录](../client-release-validation.md)。不忽略扫描、不伪造依赖版本。2026-11-01 新披露的 39 条 pillow advisory 全部指向 13.0.0，而 13.0.0 要求 Python ≥ 3.11（12.3.0 是最后一个支持 3.10 的版本），因此在 Python 3.10 上没有可用修复版；按 G1 规则严重与高危漏洞不得豁免，处理方式是升级运行时到 3.11（见 `openspec/changes/backend-python-311/`），不做风险豁免、不加忽略扫描配置。

新增迁移 `b7e2c4a91d30`（media_assets 加 position）已校验 revision 图为单头、链长21、无悬挂引用；**未在真实库执行 upgrade/downgrade**，新增的媒体顺序后端用例也未执行（当前环境无 Docker / PostgreSQL / Redis）。

此外尚未取得：

- 实际主体/备案/社区类目与商店准入、正式隐私政策、SDK清单和可响应的支持渠道。
- 目标PostgreSQL15/Redis7完整CI，真实镜像与密钥扫描，独立越权/隐私数据流复核。
- 本次新增的媒体顺序后端用例与迁移 `b7e2c4a91d30` 尚未在真实隔离PostgreSQL上执行；需在测试库跑通后再勾选。
- 私有COS访问与所有副本删除、腾讯审核真实额度/费用、**进程杀死和 Redis/DB 依赖故障演练已于 2026-11-03 在专用隔离环境完成实测**（杀 worker 后租约 **0.626 秒**被重新领取、连续失败 **5 次**进入死信 `dead`、退避 **2/4/8/16 秒**、供应商故障期间内容保持待审不公开、人工决定不被旧 worker 覆盖、Redis/DB 故障时 `/health/ready` 返回 **503**、故障期间**半成品数据 0**、恢复时间 **3.88 / 4.45 秒**，见「G2 可靠性：隔离环境故障注入演练」小节；其中「PostgreSQL 不可达时写路径返回 500 而非 503」的缺陷**已于 2026-11-04 修复并复测**（写路径 **500 → 503**，恢复 **5.32 秒**，恢复后写入成功且无半成品数据，见「G2 可靠性：PostgreSQL 不可达时写路径错误码修复复测」小节））；**仍未取得**：真实告警送达与人工确认、目标环境复测、真实腾讯云审核接口的额度/费用/SLA。
- 同一制品预发布、异机备份、备份加密、WAL 归档/PITR 和真实告警确认仍未取得（**应用回滚与完整恢复已在 2026-11-03 的隔离环境实测通过**，见上文「G2 可靠性：隔离环境备份 / 恢复 / 应用回滚演练」小节）；RPO≤1小时、RTO≤4小时仍是目标 —— 隔离环境实测的 RPO 6.457 秒只是纯逻辑备份口径，不是 PITR 承诺。
- 1万用户/10万帖/50万评论下100req/s30分钟、200req/s5分钟及8小时长稳，p95与5xx验收；当前不声称承载500在线。
- 正式HTTPS域名的浏览器多标签与跨端联调，微信真机、Android签名包/安装升级/Keystore及SDK隐私行为。
- Web按50→200→全校的真实试运营、平台审核。

完整状态见[交付状态](implementation-status.md)、[发布门禁](release-gates.md)、[证件删除验收](../student-verification.md)。各阶段未执行项保持未勾选，禁止填虚构报告绕过门禁。

## 复验入口

后端：按README设置独立*_test数据库与Redis13/14/15，执行python -m pytest -q；pytest会清理该测试数据。运维：python -m unittest discover -s scripts/tests -v。前端：Node22.12+下npm ci，generate:api、type-check、test、build:h5、build:mp-weixin、build:android；管理台type-check及build。两个前端分别执行官方npm audit。浏览器走查需 Playwright Chromium：先构建产物，再执行 `frontend/scripts/all-pages-walkthrough.py` 与 `admin-frontend/scripts/all-views-walkthrough.py`（另有各页面/视图的专项走查脚本）。迁移与恢复脚本只允许显式ACK的隔离库，见运行手册及CI。

本次临时测试数据库和依赖位于被忽略的.pytest_cache，不属于生产基础设施；回归结束后已关闭55432/56379专用测试进程，未修改开发或生产数据库；私有媒体和证件目录同样已排除版本管理。首次迁移需备份、维护窗口和全员重新登录；旧认证和原始姓名/学号清理不可由downgrade还原。