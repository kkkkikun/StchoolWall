## Purpose

记录 SchoolWall 中发现的优化点（性能瓶颈、代码异味、技术债务）与改进方向，含当前影响、建议方案、优先级，持续提升代码质量与性能。发现即记录，完成即更新状态。

> 版本：1.0 ｜ 最后更新：2026-07-06
> 初始为空模板。开发与 review 过程中按下方格式追加条目。

## Requirements

### Requirement: 优化点记录

发现的性能、重复、复杂度问题 MUST 记录，含当前影响与建议方案。

#### Scenario: 发现优化机会

- **WHEN** 开发者发现性能问题、重复代码、过度复杂设计、技术债务
- **THEN** 在下方"优化点清单"追加条目，格式为：
  - **[优先级: 高/中/低]** 问题描述
    - 当前影响：
    - 建议方案：
    - 验证方式：

#### Scenario: 评估优化价值

- **WHEN** 需要决定是否做某项优化
- **THEN** 参考清单中的优先级与当前影响，权衡收益与改动范围

### Requirement: 优化完成追踪

已完成的优化 MUST 标记状态并保留历史。

#### Scenario: 完成优化

- **WHEN** 某项优化落地并验证
- **THEN** 将对应条目标记为 **[已完成]**，补注完成日期与实际效果

### Requirement: 优化优先级管理

优化点 MUST 按优先级排序，合理安排顺序。

#### Scenario: 规划优化计划

- **WHEN** 制定优化计划
- **THEN** 优先处理高优先级条目；低优先级条目可在相关模块改动时顺手清理（遵循 Surgical Changes）

---

## 优化点清单

> 记录于 2026-10-31。数据来自当时的实测（管理台首屏 gzip 411KB、主前端三端产物、管理台/主前端 npm audit 结果）。

- **[优先级: 高] [已完成 2026-10-31]** 管理台 Element Plus 全量引入，首屏 JS 362KB gzip

  - 当前影响：`admin-frontend/src/main.ts` 用 `app.use(ElementPlus)` + 全量 CSS。产物主 chunk 1.1MB raw、首屏合计 411KB gzip（JS 362K + CSS 49K），但全项目只用到 41 种 `el-*` 组件。管理台是运营方每天要开的后台，弱网下首屏明显偏慢。
  - 已完成：改用 `unplugin-vue-components` + `unplugin-auto-import` 的 `ElementPlusResolver` 按需引入，CSS 同步按需。locale 由 `app.use(ElementPlus, {locale})` 改为 `provideGlobalConfig({ locale: zhCn }, app)`（不注册全部组件的前提下仍提供中文 locale，已实测 MessageBox 按钮为「取消/确定」）。**实测首屏 411KB → 102KB gzip（-75%）、1458KB → 303KB raw（-79%）；主 chunk 1099KB → 249KB raw；全部 CSS 353KB → 264KB raw / 45KB gzip。**
  - 踩坑（务必留意）：① Element Plus 按需注入的组件样式会在 `main.ts` 的样式 import **之后**进入产物，同特异性下后加载者胜，Element Plus 默认蓝（#409eff）会反过来盖掉玫瑰红，导致全视图走查 34/34 全挂（按钮变默认蓝、文字对比度掉到 2.0~3.1:1）。解法：`theme.css` 的选择器提到 `html:root`（0,1,1 > `:root` 0,1,0）与 `html.dark:root`（0,2,1 > `html.dark` 0,1,1），与注入顺序解耦。② `el-table` 的 slot 行类型固定为 `DefaultRow`，组件一旦被 `components.d.ts` 声明出真实类型，原先被 `any` 掩盖的 42 处类型不匹配全部暴露；已在模板里用 `row as X` 标注，并把 el-tag 的状态映射表标注为 `TagProps['type']`。③ `unplugin-*` 生成的 dts 必须**提交入库**，否则 CI 里先跑的类型检查拿不到声明；且 `build` 脚本改为 `vite build && vue-tsc --noEmit`（先出 dts 再校验），避免「类型报错 → 构建不执行 → dts 不更新」的死锁。④ 服务型 API 的样式由 AutoImport 注入到**各视图 chunk**，而真正调用 ElMessage 的 `request.ts` 在主 chunk，首屏提示会没有样式；解法：服务型 API 的样式在 `main.ts` 显式引入进主 chunk。⑤ 被单元测试直接加载的源码（`request.ts`）不能依赖构建期自动注入，其 `ElMessage` 保留显式导入（`element-plus/es`，与包根同一模块实例，测试的 monkey-patch 仍生效），样式则挪到 `main.ts` 引入以免 .css 让 Node loader 报 ERR_UNKNOWN_FILE_EXTENSION。
  - 验证方式：构建后比对 `dist/assets/index-*.js` 与 `index-*.css` 的 gzip 体积；跑 `admin-frontend/scripts/all-views-walkthrough.py`（34/34）确认 41 种组件仍全部挂载且主题色未被覆盖；跑 `admin-frontend/scripts/style-coverage-check.py` 确认样式齐全（已做负向验证：抽掉主 chunk 的 message 样式即失败）。

- **[优先级: 高] [已完成 2026-10-31]** 管理台 echarts 整包懒加载块 372KB gzip

  - 当前影响：`DashboardView.vue` 用 `import('echarts')` 动态加载，已做到不进首屏；但整包 1.1MB raw，打开看板即下载 372KB gzip。
  - 已完成：新增 `admin-frontend/src/utils/echarts.ts` 收口注册 —— `echarts/core` + `LineChart`（看板只有折线）+ `GridComponent` / `TooltipComponent` / `LegendComponent` / `AxisPointerComponent`（tooltip 的 `trigger:'axis'` 依赖轴指针）+ `CanvasRenderer`。`DashboardView.vue` 改为动态 `import('@/utils/echarts')`，仍不进首屏。**实测懒加载块 1135.53KB → 526.99KB raw（-54%）、382.15KB → 180.06KB gzip（-53%）**，落在预估的 150~200KB 区间内。
  - 踩坑（务必留意）：echarts 6 的 `sideEffects` 把 `lib/chart/*.js` / `lib/component/*.js` 标成有副作用，所以「整包 `import('echarts')` 再 tree-shake」是行不通的 —— 必须走 `echarts/core` 等 ESM 子路径做**模块级**按需注册（`echarts/charts`、`echarts/components`、`echarts/renderers`），未用到的图表类型才会被 Rollup 丢掉。另外新增图表类型时必须在 `utils/echarts.ts` 同步注册，否则运行时报「组件未注册」；`echarts/core` 的 `ECharts` 类型要从 `echarts/core` 取（不是 `echarts`），否则类型检查会把整包拉回依赖图。
  - 验证方式：构建后比对 `dist/assets/echarts-*.js` 的 gzip 体积；跑 `admin-frontend/scripts/dashboard-walkthrough.py`（9/9）确认 canvas 非空、图表几何无重叠、图例与坐标轴文字仍取主题色。

- **[优先级: 中] [已完成 2026-10-31]** 前端性能基线未入库、无回归门禁

  - 当前影响：`frontend/scripts/ui-perf-audit.py` 把首屏指标写到 `/tmp/audit/metrics.json`，不入库、不比阈值。性能是否退化目前没有任何自动判定，只能靠人肉看。
  - 已完成：新增 `frontend/scripts/perf-budget-check.py`，基线存 `frontend/perf-baseline.json`（入库）。**硬门禁只卡产物体积**（首屏 JS/CSS、全量 JS/CSS、最大单块，均为 gzip -9 字节数）—— 体积是确定性的，同样代码必然得到同样数字，可以严格卡阈值，超过基线 10% 即非零退出。**运行时指标（FCP / DOMContentLoaded / LCP）只采集不拦截**：受 CI runner 负载影响很大，硬卡会造成随机失败，因此只写进报告供横向比较。管理台同构新增 `admin-frontend/scripts/bundle-budget-check.py`（基线 `admin-frontend/bundle-baseline.json`），守住首屏与 echarts 按需注册的成果。两者均已接入 CI。
  - 实测基线：学生端首屏 JS 102.9KB gzip / 首屏 CSS 8.4KB gzip / 全量 JS 169.9KB gzip / 全量 CSS 30.5KB gzip；管理台首屏 JS 93.3KB gzip、echarts 块 174.9KB gzip、全量 JS 483.0KB gzip。两种 `--base` 构建形态下门禁都稳定通过。
  - 验证方式：正常跑 exit 0；人为把基线调小 30% 即 exit 1 并指出超出的项；恢复后重新 exit 0。

- **[优先级: 中] [已完成 2026-10-31]** 图标「注册表唯一来源」名存实亡

  - 当前影响（**原记述已过时，实测修正**）：`openspec/specs/frontend-ui/spec.md` 要求「一律通过 `utils/icons.ts` 注册表引用，不得手写路径」，实际 91 个路径（183 处引用、22 个文件）直接写死 `<image src="/static/icons/...">`。**「207 个 SVG 里 103 个零引用」的说法不成立** —— 实测磁盘 207 个 SVG 与注册表 207 条路径一一对应，零引用为 0；真正的缺口只是「引用没走注册表」，一旦生成器调整路径，这 91 个手写路径就会静默 404。
  - 已完成：把 91 个手写路径全部改写为注册表引用（模板 `:src="ICONS['x']"` / `:src="ICON_TONES['x']['tone']"`，脚本与 TS 用同一表达式），并在 22 个文件按需补 `import { ICONS, ICON_TONES } from '@/utils/icons'`。**没有改成 `<UiIcon>` 组件**：那会换掉 `<image>` 标签与类名、改动每个图标的尺寸语义，回归面远大于收益。新增 `frontend/scripts/icon-consistency-check.py` 做静态守卫：断言磁盘 SVG ↔ 注册表一一对应、注册表路径格式合法、**源码里不再出现手写 `/static/icons/...` 字面量**，已接入 CI。
  - 连带改动：3 个单元测试（`navigation` / `mp-login` / `web-login-guard`）用 Node loader 直读 SFC 源码、绕过 vite，`@/utils/icons` 别名无法解析导致 55 项里挂 3 项。已抽出共享 helper `frontend/tests/helpers/compile-ts.mjs`，让测试加载**真实**注册表源码（而非各自 mock），三处测试均恢复通过。
  - 验证方式：守卫 exit 0（207 个 SVG ↔ 208 个语义名一一对应、源码无手写路径）；负向验证两条 —— 临时把某个页面改回手写路径 → exit 1；临时删掉一个 SVG → exit 1；恢复后 exit 0。全页面走查 57/57、对比度审计 0 缺陷，三端构建产物里图标各 207 个。

- **[优先级: 低] [部分完成 2026-11-01]** 残余 moderate 依赖告警（构建期，不进产物）

  - 当前影响（2026-11-02 官方 registry 实测）：主前端 20 moderate（17 条来自 `@intlify/core-base` 两条 advisory，3 条来自 `openapi-typescript` → `@redocly/openapi-core` → `minimatch` globparts 放大 ReDoS，GHSA-g3hv-75wg-m249），管理台 **0 vulnerabilities**（2026-11-01 起 `minimatch` 依赖链已消失，见下方「已完成」条目）。均为 devDependency 传递链，实测客户端产物中不含相关代码，**0 high / 0 critical**。原始审计输出见 `release/frontend-audit.json`（全量，20 moderate）与 `release/frontend-audit-production.json`（`--omit=dev`，16 moderate），2026-11-02 用官方 `https://registry.npmjs.org` 重跑刷新入库，命令与环境记录在 `docs/client-release-validation.md`。
  - 建议方案：主前端等 uni-cli-shared 的 `@intlify` 锁定版本推进（9.x 线内无同时避开两条 advisory 的版本，跨大版本会破坏其对 `@intlify/runtime@9.1.9` 的精确锁定）；管理台等 `@vue/language-core` 跟进 `minimatch >= 11.0.1`。**不要用 `overrides` 强行覆盖**，会破坏类型工具链。
  - 验证方式：每次升级后重跑 `npm audit --registry=https://registry.npmjs.org --audit-level=high`，并实测产物不含告警包字样。
  - 已完成（管理台侧，2026-11-01）：上游条件已兑现 —— `@vue/language-core` 从 3.0.2 起改用 `picomatch`，不再依赖 `minimatch`。管理台 `vue-tsc` 由 `^2.2.0` 升到 `~3.1.8`（连带 `@vue/language-core` 3.1.8、`@volar/*` 2.4.26），**管理台官方 npm audit 归零（0 vulnerabilities）**，`minimatch` 从依赖树中彻底消失。
  - 踩坑（务必留意）：`vue-tsc` **3.2/3.3 线对本仓库模板会误报**，升级前必须实测：① `3.3.14` 在 `BannersView.vue` 报 `Property 'value' does not exist` —— 触发条件是**属性值里含 `//`**（如 `placeholder="https://…"`，动态 `:placeholder="'https://abc'"` 同样触发），其后同模板内的其它 `v-model` 会被一起报错；Vue 编译器生成的代码本身正确（`modelValue` + `onUpdate:modelValue`），是工具侧回归。② `3.2.9` 起在 `PostsView.vue` 报 `:initial-index="idx"` 的 `string \| number` 类型错。实测 `3.0.5` / `3.0.11` / `3.1.8` 三版对本仓库均 0 错，故锁 `~3.1.8`，不升到 3.3.x。
  - 仍待上游（主前端侧，20 moderate 未变）：17 条来自 `@dcloudio/uni-cli-shared` → `@intlify/core-base` 的两条 advisory（按上文 9.x 线内无解的结论维持现状），另 3 条来自 `openapi-typescript` → `@redocly/openapi-core`（1.x 精确锁定 `minimatch@5.1.9`，2.x 才改用 `picomatch`，而 `openapi-typescript@7.13.0` 只接受 `^1.34.6`）。两者均按「不用 overrides 强行覆盖破坏工具链」的既定处置等上游，不伪造清零。

- **[优先级: 低] [已完成 2026-10-31]** 前端 7 套走查脚本仍各带一份静态服务代码

  - 当前影响：`frontend/scripts/` 下 7 个脚本各自定义了一份几乎相同的 `SilentHandler`/`QuietHandler`（H5 用 hash 路由，不需要 SPA 回退，所以比管理台那批更简单）。管理台侧已抽出共享模块 `admin-frontend/scripts/walkthrough_server.py`，前端侧尚未跟进。H5 当前部署在根路径（nginx `location /`），**不影响 CI 运行**，故本轮未动。
  - 已完成：新增 `frontend/scripts/h5_walkthrough_server.py`（`create_server(dist_dir)`），7 套脚本全部改为调用它，删掉 7 份重复的 handler 与各自选端口的样板代码。**内嵌 mock 未归入共享模块** —— `all-pages-walkthrough.py` 与 `web-login-guard-walkthrough.py` 的 mock 夹具与各自断言强耦合，强行合并反而更难维护，不是本次的目标。
  - 顺带修掉一个真实缺陷：`socketserver.TCPServer.request_queue_size` 默认只有 5，页面并发加载十几个资源时 listen 队列容易被打满，浏览器侧表现为 `Failed to load resource: net::ERR_CONNECTION_CLOSED`，走查会把它当真实控制台错误而误判失败。共享服务把 backlog 提到 128，并吞掉客户端提前断开时的 `BrokenPipeError`/`ConnectionResetError`。
  - 验证方式：7 套脚本改后逐个跑通，场景数与断言结果与改前一致（57 / 16 / 16 / 发布 / 上传 / 登录守卫 / 详情互动全部 PASS）。

- **[优先级: 高] [已完成 2026-10-31]** H5 运行时依赖 dcloud 公网 CDN（第三方外呼）

  - 当前影响：**uni-app H5 框架的 CSS 注入 `body:after` 隐藏伪元素，3 秒后从 `cdn.dcloud.net.cn/img/shadow-grey.png` 拉一张导航阴影图。** 每次打开页面都多一次外网请求 —— ① 首屏被第三方 CDN 拖住；② CDN 不可达时浏览器控制台报 `net::ERR_CONNECTION_CLOSED`，被客观缺陷扫描当成真实缺陷，**全页面走查随机挂掉**（实测 8 次里偶发 1~2 次）；③ 用户 IP 与访问时间泄漏给第三方。走查里「控制台错误 0 条但总体 FAIL」的现象此前一直没定位到根因。
  - 已完成：在 `frontend/src/App.vue` 的 H5 条件编译段里用 `html body::after { content: none; animation: none; }` 关掉该伪元素 —— 选择器比框架的 `body:after` 多一层 html（0,0,3 > 0,0,2），**不依赖样式加载顺序**。新增 `frontend/scripts/external-request-check.py` 守卫：打开主要页面时断言不向第三方域名发请求（自家 `/api/v1/**` 后端调用除外），已接入 CI。
  - 实测：修复前探针捕获 1 条外网请求（`https://cdn.dcloud.net.cn/img/shadow-grey.png`），修复后 **0 条**；负向验证 —— 往产物 HTML 塞一个 `https://example.com/pixel.png` 即 exit 1，恢复后 exit 0。
  - 备注：产物里还剩 `hac1/has1.dcloud.net.cn`（uni-app 广告模块的配置/GUID 端点）与 `vuejs.org/error-reference`（报错文案里的链接），实测**运行时均未触发**（探针 0 外呼），本项目没有广告位，不需要处理。
  - 验证方式：`python3 frontend/scripts/external-request-check.py --base-url <预览地址>`；全页面走查不再出现偶发 FAIL。

- **[优先级: 高，但需外部环境]** 真实环境验证缺口（工具链已就绪，缺环境）

  - 当前影响（2026-11-03 更新）：后端 pytest 已在目标 PostgreSQL 15 + Redis 7 上跑通（Production CI 运行 41369377491 的 verify 作业：**535 passed / 3 skipped**，运维脚本回归 20 项全 ok），迁移 `529bf8becb3f`、`b7e2c4a91d30` 的 upgrade → downgrade → 再 upgrade 与 `alembic check` 亦在同一环境通过，逻辑恢复冒烟通过，契约导出 125 paths，`pip-audit --strict` 无已知漏洞；密钥扫描（Gitleaks）通过。**镜像 Trivy 扫描实跑并失败** —— 2026-11-03 的 main 分支复跑（Production CI 运行 `41578409185`，提交 `e504709`，image 作业 job `125732883940`）已把镜像侧结论取回原始日志：导入冒烟仍打印 `built image imports and exports contract`；Trivy `Report Summary` 里 **65 个 `python-pkg` 目标逐条为 0**，全表 `Total: 45 (HIGH: 45, CRITICAL: 0)` 全部来自基础镜像 `python:3.11-slim`（Debian 13.7）的 **OS 层 45 条无修复版本 HIGH**（较 2026-11-02 的 46 条少 1 条），镜像内 `setuptools` 内置依赖那 2 条 HIGH（`jaraco.context 5.3.0`、`wheel 0.45.1`）已随 `backend/Dockerfile` 安装层内移除 `setuptools`/`wheel` 而消失。扫描失败即中止推送（带高危的镜像未发布），`openspec/changes/backend-python-311/tasks.md` 第 9 行**保持未勾选**，**未豁免、未降门禁**（未加 `.trivyignore`、未改 severity、未改 `ignore-unfixed`）。仍未取得：异机备份/PITR 与告警演练、独立人工安全复核。（**k6 容量门禁 G3 已于 2026-11-03 在专用隔离环境取得**：burst、soak（跑满 8 小时）、steady 三个场景全部达标，且 2026-11-03 补上推荐流场景后按同一口径复测 burst 通过，见 `docs/production/capacity.md` 与 `docs/production/release-gates.md` 的 G3 行。）**发布门禁 G1（镜像扫描零未豁免高危）/G2（真实恢复与告警）仍未解除。**
  - 建议方案：按 `docs/production/capacity.md` 建隔离库跑种子与 k6；镜像侧分两步 —— ① 仓库自控部分：**已完成 2026-11-02 改动、2026-11-03 取证** —— `backend/Dockerfile` 的依赖安装层内在同一层移除镜像自带的 `setuptools`/`wheel` 并断言其不再存在（运行期不需要构建工具，`setuptools/_vendor` 内置的 `jaraco.context 5.3.0`、`wheel 0.45.1` 两条 HIGH 随之消失；未豁免、未改 severity、未改应用依赖版本；命令与环境见 `docs/production/verification.md`），**权威证据已由 main 分支运行 `41578409185` 的 Trivy 报告给出：python-pkg 层 0 条**；② 基础镜像的 45 条 HIGH 在 Debian 13 尚无修复版本，只能等上游发布安全更新后重建，或改用不含 `util-linux`/`ncurses`/`perl-base`/`libsystemd0` 的镜像族 —— 后者属基础镜像族级变更，须走 `openspec/changes/` 提案与人工决策。独立安全复核需人工安排。
  - 验证方式：按 `docs/production/release-gates.md` 逐门禁保存提交、日期、环境、执行人、命令与原始报告，无证据一律保持未通过；镜像侧以 Production CI main 分支 image 作业的 Trivy 步骤退出码 0（0 HIGH / 0 CRITICAL）且导入冒烟仍打印 `built image imports and exports contract` 为准。

- **[优先级: 中] [已完成 2026-11-03]** 电脑端 `desktop-frontend/` 的体积预算、浏览器走查与深色对比度未入门禁

  - 当前影响：电脑端已接入 CI 的 type-check / node --test / build / `npm audit --audit-level=high`，接口漂移也已被契约守卫覆盖，但与另外两个前端相比仍缺三道门禁 —— ① **没有体积基线**：学生端有 `frontend/perf-baseline.json`、管理台有 `admin-frontend/bundle-baseline.json`，桌面端没有，依赖升级带来的主 chunk 膨胀不会被当场抓住（当前实测产物 752KB、主 chunk 361KB raw / 132KB gzip）；② **没有浏览器级走查脚本**：H5 与管理台的 UI 回归覆盖不到电脑端；③ **深色模式与对比度没有客观扫描**，亮/暗两套配色目前只有人工目视。
  - 建议方案：仿 `admin-frontend/scripts/bundle-budget-check.py` 新增 `desktop-frontend/scripts/bundle-budget-check.py`（基线 `desktop-frontend/bundle-baseline.json`），新增 `desktop-frontend/scripts/*-walkthrough.py`（Playwright，覆盖信息流 / 帖子详情 / 登录 / 发帖四条关键路径），两者接入 CI；深色与对比度断言沿用 `frontend/scripts/ui-contrast-audit.py` 的令牌化做法（断言基于令牌而非色值）。注意电脑端 base 是 `/pc/`，走查必须按该前缀访问，否则会走查失败（管理台曾因 `--base=/admin/` 不匹配导致 34 场景全挂）。
  - 验证方式：正常跑 exit 0；人为把基线调小 30% 即 exit 1 并指出超出的项；走查四条关键路径全 PASS 且 console 错误为 0；`openspec validate --specs` 通过。
  - 已完成：新增三道门禁并接入 Production CI —— ① `desktop-frontend/scripts/bundle-budget-check.py` + 基线 `desktop-frontend/bundle-baseline.json`（按 2026-11-03 实际产物定，未放宽：主 chunk 370356 B raw / 134576 B gzip、全量 JS 571913 B raw / 214098 B gzip、全量产物 713864 B raw，容差沿用另外两个前端的 10%）；② `desktop-frontend/scripts/ui-walkthrough.py`（Playwright，19 项断言全 PASS、控制台错误 0 条，按 `/pc/` 前缀访问），配套抽出 `walkthrough_server.py`（静态服务 + 前缀剥离）与 `desktop_mock_api.py`（信封格式接口夹具，不含任何真实用户数据）；③ `desktop-frontend/scripts/ui-contrast-audit.py`（亮/暗两套配色 × 四条关键路径，断言基于 `src/styles/tokens.css` 的令牌：正文令牌 --sw-text 在页面底/卡片底 ≥4.5:1、白字压主色 ≥4.5:1、主色压亮底 ≥4.5:1、源码不得引用未定义令牌；实测阻断项 0 条）。新增单元测试 `scripts/tests/test_desktop_ci_gates.py`（19 项）随运维脚本回归一起跑。
  - 踩坑：走查必须按 `/pc/` 前缀访问，且 **SPA 回退不能把缺失的静态资源回成 index.html**（会把 .js 请求变成 HTML，浏览器报解析错误被误判成真实缺陷）；另外电脑端的会话只在内存里，刷新页面要走刷新通道换回来，因此接口夹具必须记住「是否登录过」并在 `/auth/refresh` 上返回会话，走查才能验证「刷新后会话恢复」。
  - 负向验证：体积基线调小 30% → exit 1 并逐项指出超出的指标；把正文令牌改成低对比度色值 → 对比度门禁 exit 1。

- **[优先级: 中] [已完成 2026-11-03]** 电脑端弱化文字、占位符与暗色品牌小字未达对比度规范

  - 当前影响：`desktop-frontend/scripts/ui-contrast-audit.py` 首次客观扫描（亮/暗两套配色 × 四条关键路径）实测 80 处未达 4.5:1 的文字，全部属于**既有配色**而非新引入的缺陷：① 品牌色小字 37 处，最低 3.22:1（`--sw-primary` #c2455c 压暗色 `--sw-primary-soft` #341c22）—— `openspec/specs/frontend-ui/spec.md` 要求暗色下品牌小字用提亮的 `--primary-text` 令牌并在全部暗底上 ≥4.5:1，电脑端 `tokens.css` 尚无该令牌；② 弱化文字 31 处，最低 2.84:1（`--sw-text-muted` #8b949e 压 `--sw-bg` #f5f6f7）；③ Element Plus 默认色 11 处：占位符 #a8abb2 在白底仅 2.30:1（规范要求 ≥4.0:1）、禁用态 #a9a9a9 配白字仅 2.35:1、次要文字 #909399 仅 3.08:1。
  - 建议方案：按 `openspec/specs/frontend-ui/spec.md` 的既有阈值补令牌（暗色专属品牌文字令牌、收紧 `--sw-text-muted`、覆写 Element Plus 的 `--el-text-color-placeholder` / `--el-disabled-*`），并把对比度脚本里这几类从「观察项」升级为阻断项。**属配色决策，本次门禁建设未擅自改动**，先记录在案。
  - 验证方式：`cd desktop-frontend && python3 scripts/ui-contrast-audit.py` 退出码 0 且观察项归零；`python3 scripts/ui-walkthrough.py` 仍 19 项全 PASS、控制台错误 0 条。
  - 已完成（2026-11-03）：按规范已写明的阈值补齐令牌并把门禁升级为阻断项 —— ① `tokens.css` 新增品牌小字令牌 `--sw-primary-text`（亮色 #ad3649 / 暗色 #e07087），品牌**填充**仍用 `--sw-primary`（与学生端 `--primary` / `--primary-text` 的分工一致），页底 / 卡片底 / 品牌浅底全部 ≥4.5:1；② 收紧 `--sw-text-muted`（亮色 #8b949e → #626d7a、暗色 #7d8792 → #8b949e），页底与卡片底均 ≥4.5:1（原最低 2.84:1）；③ 覆写 Element Plus 默认色：`--el-text-color-placeholder` / `--el-text-color-secondary` / `--el-text-color-disabled` / `--el-disabled-*` 全部取本仓库令牌，占位符白底 5.27:1、次要文字 6.39:1、禁用文字 5.27:1（禁用底 4.91:1），并补上语义色 success/warning/danger/info（默认色白底只有 2.0~3.1:1）；暗色下 `--el-color-primary` 提亮为 #e07087 承担品牌**文字**，实心主按钮与选中态单选按钮组的填充压深到 #b03e53 保证白字 5.74:1（与管理台 `theme.css` 的暗色口径一致）；④ `desktop-frontend/scripts/ui-contrast-audit.py` 把品牌色文字 / 弱化文字 / 次要文字 / 其他令牌 / 字面量色值 / 占位符六类由观察项升级为阻断项（阈值取自规范：正文 ≥4.5:1、占位符 ≥4.0:1、大字 ≥3:1，未放宽），并新增令牌级断言（品牌小字与弱化文字在各自底色、Element Plus 占位符/次要/禁用文字在卡片底与禁用底）。**实测：阻断项 0 条、观察项 0 条**（改前 80 条观察项）。
  - 连带修掉的两处既有缺陷：① 首页轮播位的暗化层按「最亮底色」也压不到白字 4.5:1（实测 2.35:1），已把渐变暗化层调整为 `rgb(0 0 0 / 60%) → rgb(0 0 0 / 90%)`；② 品牌浅底 `--sw-primary-soft` 压品牌主色只有 4.34:1（Element Plus 的 plain 按钮与 plain 标签都落在这个底色上），已压到 #fdf6f7（4.58:1）。
  - 负向验证：把 `--sw-text-muted` 改回 #8b949e → 对比度门禁 exit 1 并逐条指出「弱化文字 / 占位符未达标」；恢复后 exit 0。走查仍 19/19 PASS、控制台错误 0 条，体积基线按改后实际产物重定（CSS +1743 B raw / +272 B gzip，来自新增的令牌与覆写规则，JS 体积不变）。


- **[优先级: 高] [已完成 2026-11-03]** 热点帖单行写锁瓶颈（详情页浏览数自增 + 点赞 `SELECT ... FOR UPDATE` 争同一 tuple）

  - 当前影响：`docs/production/capacity.md` 的 2026-11-02 实测里，burst（200 req/s × 5 分钟）未通过 —— 读 p95 2743.72ms / 写 p95 4063.85ms、dropped iterations 9624、实际只有 167.36 req/s；PostgreSQL 日志（`log_lock_waits=on`）记录到同一 tuple 上最长 **38 个进程**的锁等待队列，慢语句集中在 `UPDATE posts SET view_count=...`（详情页浏览数自增），而场景本身要求 80% 详情集中在单热点帖 —— 于是热点帖的 `posts` 行成了全局串行点。
  - 建议方案（本文档「报告与优化」一节已列明的「异步浏览聚合」）：浏览数改为写入独立的聚合缓冲表、由 worker 周期性折叠回 `posts.view_count`；互动路径去掉对 `posts` 行的 `SELECT ... FOR UPDATE`，计数改原子自增。
  - 已完成（2026-11-03）：① 新增 `post_view_counters` 表（Alembic `c1d2e3f4a5b6`），详情页只写缓冲表（`INSERT ... ON CONFLICT DO UPDATE` 原子自增），后台 worker 每 10 秒逐帖一个小事务折叠回 `posts.view_count`，详情接口返回「已折叠值 + 待折叠增量」（同一条语句的一致快照）；② 点赞/取消赞/评论/收藏去掉 `SELECT ... FOR UPDATE`，计数改原子自增并 `RETURNING`，计数语句不再依赖 `posts.status`（帖子被隐藏时计数不漂移）；③ 新增后端用例 `backend/tests/test_hot_post_counters.py`（8 项），含「外部事务锁住热点帖行时详情请求不被阻塞」的回归。
  - 验证方式：隔离环境（专用 KVM 虚拟机 + 容器化 PostgreSQL 15 / Redis 7，1 万用户 / 10 万帖 / 50 万评论合成数据）按 `docs/production/capacity.md` 的同一脚本复测 —— burst 由**未通过转为通过**：实际 199.69 req/s、读 p95 340.16ms、写 p95 20.11ms、dropped iterations 0、5xx 0、429 0；压测窗口内 `log_lock_waits` 记录 0 次行锁等待、0 条 >500ms 慢语句。soak（100 req/s × 8 小时）于 2026-11-03T05:56:35Z 在同一环境启动、**13:56:35Z 跑满 8 小时整**（2,880,000 次迭代、99.999 req/s、读 p95 345.78ms、写 p95 15.54ms、dropped iterations 0、5xx 0、429 49,086 次单列后成功吞吐 100.00%），窗口内 `log_lock_waits` 仍为 **0 次**行锁等待；API 进程 RSS 全程 483MB 几乎不变、PostgreSQL 内存进入平台期，**无持续资源增长**，压测停止后 6 秒内 CPU 由 73.7% 回落到 0.7%（恢复耗时 < 1 分钟）。计数一致性：全库 `like_count` / `comment_count` 不一致帖数均为 **0**；任务恢复：租约过期后 ≤2.1 秒被重新领取，连续失败 5 次后进入死信 `dead`。
  - 踩坑（务必留意）：计数缓冲表**不能加到 `posts.id` 的外键** —— 外键检查会对父行取 KEY SHARE 锁，与 `FOR UPDATE` 互斥；一旦加上，详情页浏览会重新被热点帖行锁挡住，串行点原样回来（本次已实测确认：`FOR UPDATE` 持锁时 `INSERT INTO footprints` 会被外键检查挂住，`FOR NO KEY UPDATE` / `FOR SHARE` 则不冲突）。同理，计数语句不要依赖 `posts.status`，否则帖子被隐藏时计数会与 `likes` / `comments` 表漂移。

- **[优先级: 高] [已完成 2026-11-03]** 帖子列表类查询的全表扫描（搜索的 `ILIKE` 与推荐流的热度分排序）

  - 当前影响：消除热点帖单行写锁后，2026-11-03 的 8 小时长稳窗口内 **57 条 >500ms 慢语句**里 53 条是帖子列表/详情共用的 `SELECT posts.*, users.* ...` 查询（PostgreSQL 日志按 `track_activity_query_size` 截断到 1024 字节，看不到 WHERE/ORDER BY 部分），**同窗口行锁等待 0 次 —— 与行锁无关**。逐条 `EXPLAIN (ANALYZE, BUFFERS)`（1 万用户 / 10 万帖 / 50 万评论）定位到两条全表扫描：① 搜索 `/api/v1/posts/search?q=…` 用 `content ILIKE '%q%'`，走 **Parallel Seq Scan（posts 31,667 行）** → Hash Join → Sort，单次 **74.961ms**（占压测流量 7%，直接抬高读 p95）；② 推荐流 `/api/v1/posts`（不带 `order`，按 `_hot_score` 热度分排序）走 **Parallel Seq Scan → Sort**，单次 **662.276ms** —— 热度分含 `now()`，无法用表达式索引直接排序；该路径是学生端默认首屏（推荐位），k6 脚本只打 `order=time` 的最新流，故未进入本轮压测流量。对照：热帖榜 `/api/v1/posts/hot` 靠 `ix_posts_created_at` 把候选集收窄到 7 天（7,238 行），单次仅 **15.733ms**。
  - 建议方案：按 `docs/production/capacity.md`「报告与优化」一节已列明的方向 —— ① 搜索：改用 PostgreSQL 全文检索或 `pg_trgm` GIN 索引，把 `ILIKE '%q%'` 从顺序扫描变成索引扫描（需评估索引体积与写入代价）；② 推荐流：**榜单预计算** —— 把热度分按固定周期（如 1 分钟）在 worker 内算好并落到物化表/物化视图（含 `(score, id)` 索引），查询只做索引扫描 + 键集分页。**不改变热度分公式本身**，以免改变推荐结果的可解释性。
  - 已完成（2026-11-03，Alembic 迁移 `d7e8f9a0b123`）：① **搜索走 `pg_trgm` GIN 索引** —— `posts.content` 新增 `ix_posts_content_trgm`（`gin_trgm_ops`），`ILIKE '%q%'` 的**子串匹配语义完全不变**（大小写不敏感、`%`/`_` 仍转义）；另加 `ix_posts_featured_id` 复合索引支撑搜索/精华流的排序与键集分页（原先排序必须全表扫描后再 Sort）。选 `pg_trgm` 而不是全文检索：全文检索是分词匹配，会改变搜索结果语义（子串、英文词干、大小写），与「不得因实现方式改变搜索结果语义」冲突。`pg_trgm` 是 PostgreSQL 官方 contrib 的 **trusted 扩展**（非超级用户只要有建扩展权限即可安装），扩展与索引都由迁移创建，回滚只删索引与表、**保留扩展**（扩展可能被运维或其它对象共用，删扩展会让回滚变成破坏性操作）。② **推荐流走榜单预计算** —— 新增 `post_hot_scores`（`(score, post_id)` 索引）与 `post_hot_score_state` 两张表，worker 每 60 秒把热度分算好落表（一个事务内完成，读接口只会看到上一轮或新一轮榜单），查询只做 `Index Only Scan Backward` + 键集分页；**热度分公式本身不变**（单一来源 `hot_score_expr`，预计算与实时两条路径共用），榜单缺失或过期（worker 停了）时读接口自动退回实时计算，结果口径一致。榜单表刻意不加到 `posts.id` 的外键（同 `post_view_counters` 的取舍：外键检查会对 posts 行取 KEY SHARE 锁）。
  - 验证方式（隔离环境，**同一 k6 脚本、同一 1 万用户 / 10 万帖 / 50 万评论数据集**，本机 PostgreSQL 15.14，同一实例前后对比）：`EXPLAIN (ANALYZE, BUFFERS)` —— 改前推荐流 `Parallel Seq Scan → Sort` **109.478ms**、搜索 `Parallel Seq Scan → Hash Join → Sort` **90.854ms**；改后推荐流首页 `Index Only Scan Backward (ix_post_hot_scores_rank)` **0.893ms**、推荐流翻页（键集 `Index Cond: ROW(score, post_id) < ROW(...)`）**0.821ms**、搜索 `Index Scan Backward (ix_posts_featured_id)` **0.504ms**、搜索（稀有词）`Bitmap Index Scan (ix_posts_content_trgm)` **0.548ms** —— **全部无全表 Seq Scan 且单次 < 50ms**。burst（200 req/s × 5 分钟）复测数值见 `docs/production/capacity.md`；后端用例（新增 `backend/tests/test_hot_scores.py` 12 项，全量 572 passed / 3 skipped）、迁移链（`upgrade → downgrade → 再 upgrade` + `alembic check` 无差异）与 API 契约（132 paths 不变）由本地隔离环境与 Production CI 判定。
  - 待人工决策：预计算周期（本次取 **60 秒**）与 `pg_trgm` 扩展的引入属基础设施与产品口味，已按「不改变搜索语义 / 不改变热度分公式」的约束择一实现并记录在案；生产库账号在官方 `postgres` 镜像里是超级用户，`CREATE EXTENSION pg_trgm` 可直接执行，若改用非超级用户需确认其有建扩展权限。
  - 已补齐压测口径（2026-11-03，`scripts/load/campus.js` + PR #38）：推荐流 `/api/v1/posts`（不带 `order`）此前**不在压测流量里**（脚本只打 `order=time` 的最新流），容量证据缺这一条；现把推荐流纳入场景配比 —— **既有七项的权重与相对比例保持不变**（45/25/10/7/6/4/3），只新增推荐流权重 10，循环长度 100→110 ⇒ 有效占比 最新流 40.9%、详情 22.7%、热榜 9.1%、搜索 6.4%、赞/取消 5.5%、评论 3.6%、未读 2.7%、**推荐流 9.1%**；脚本另按场景分列请求数与时延（`scenario_<name>_count` / `scenario_<name>_duration`）。隔离环境按同一口径复测 burst（200 req/s × 5 分钟，`2026-11-03T21:30:50Z → 21:35:54Z`，同一实例同一数据集）：实际 **199.893 req/s**、读 p95 **23.26ms**、写 p95 **18.37ms**、dropped iterations **0**、5xx **0**、429 **68 次**单列、业务成功率 **99.887%**；**推荐流路径实测 p95 18.19ms / p99 27.75ms**，其 `EXPLAIN (ANALYZE, BUFFERS)` 为 `Index Only Scan Backward (ix_post_hot_scores_rank)` + `posts_pkey`/`users_pkey` 索引扫描、Execution Time **0.860ms**、无全表 Seq Scan、单次 < 50ms；压测窗口内行锁等待 **0 次**，>500ms 慢语句 5 条全部是 worker 每约 63 秒一次的榜单刷新（非用户请求路径）。数值见 `docs/production/capacity.md`，守卫用例见 `scripts/tests/test_load_campus_mix.py`。

- **[优先级: 中] [已完成 2026-11-04]** PostgreSQL 完全不可达时写路径返回 500 而非 503（依赖不可用的错误码语义不一致）

  - 当前影响（2026-11-03 隔离环境故障注入演练实测）：停止 PostgreSQL 容器后，`/health/ready` 正确返回 **503**（`{"status":"unavailable"}`）、`/health/live` 仍 **200**、**写入不产生半成品数据**（各表计数逐项比对一致），但**写路径返回 HTTP 500**（`{"code":500,"message":"服务暂时不可用"}`，API 日志 `event=unhandled_error`），而同一环境里 Redis 不可用时写路径返回的是 **503**（`{"code":503,"message":"安全校验服务暂时不可用，请稍后重试"}`）。根因已定位：数据库连接被拒时 SQLAlchemy 抛出的 `ConnectionRefusedError` 是 `OSError` 子类、**不是 `SQLAlchemyError`**，因此 `backend/app/main.py` 的 `database_error` 处理器（返回 503「数据服务暂时不可用」）没有接住它，异常一路落到 `request_context` 中间件的兜底 `unhandled_error` 500 分支。
  - 影响面：数据正确性不受影响（无半成品写入、就绪探针行为正确），但**错误码语义不一致** —— 依赖不可用被报成 500 而不是 503，会被计入 5xx 错误预算（发布门禁的 5xx<0.1% 口径），也会误导告警按「服务内部错误」而非「依赖不可用」分类。
  - 建议方案：在 `backend/app/main.py` 为数据库连接类异常补一个处理器（捕获 `sqlalchemy.exc.SQLAlchemyError` 之外的连接层 `OSError`/`ConnectionError`，或统一用 `sqlalchemy.exc.DisconnectionError`/`DBAPIError` 基类），返回与 Redis 一致的 **503「数据服务暂时不可用，请稍后重试」**；**不改接口契约、不改业务语义**，只改错误码与文案。
  - 验证方式：隔离环境停 PostgreSQL 容器 → 写路径状态码由 500 变为 **503**、body 为 `{"code":503,"message":"数据服务暂时不可用，请稍后重试"}`；恢复后 `/health/ready` 回到 200、写入恢复成功且仍无半成品数据；新增后端用例断言「数据库连接失败时返回 503 而非 500」。后端用例与 API 契约由 Production CI 判定。
  - 处置状态：**本工单（故障注入演练）未擅自改动生产代码**，仅如实记录；是否修复属人工决定项。
  - 已完成（2026-11-04）：按本条目已写明的建议方案落地 —— ① `backend/app/main.py` 新增 `OSError` 异常处理器：数据库连接被拒时 SQLAlchemy 抛出的 `ConnectionRefusedError` 是 `OSError` 子类、不是 `SQLAlchemyError`，原来的 `database_error` 处理器接不住，异常一路落到 `request_context` 中间件的兜底 `unhandled_error` 500 分支；现在**连接层异常**（`ConnectionError` / `TimeoutError` / `socket.gaierror`）统一返回 **503「数据服务暂时不可用，请稍后重试」**，与 Redis 不可用的错误码语义一致；**与依赖无关的 `OSError`**（文件读写失败等）仍按内部错误 500 处理，不改写既有语义（避免把磁盘/权限类故障误报成「数据服务不可用」）。② 新增后端用例 `backend/tests/test_db_unavailable.py`（3 项）：写路径数据库连接失败返回 **503**（不是 500）、就绪探针 503 / 存活探针 200、与依赖无关的 `OSError` 仍为 500。**接口契约与业务语义未变，只改错误码与文案。**
  - 实测（2026-11-04，专用隔离环境：容器化 PostgreSQL 15.14 / Redis 7.4.7，合成数据 20 用户 / 100 帖，**独立库 `schoolwall_drill_loadtest` + 独立 Redis 逻辑库 15**，k6 数据集未被写入）：同一套合成数据与账号下同时启动「修复前」「修复后」两份 API，停同一个 PostgreSQL 容器后对照 —— 写路径状态码 **500 → 503**，响应体由 `{"code":500,"message":"服务暂时不可用"}` 变为 `{"code":503,"message":"数据服务暂时不可用，请稍后重试"}`；故障期间 `/health/ready` 仍 **503**（0.003468 秒）、`/health/live` 仍 **200**；恢复容器后 **5.32 秒** `/health/ready` 回到 200，随后写入 **HTTP 200**（`post_id=101`）成功；**无半成品数据** —— 基线计数 `posts/jobs/comments/media_assets/moderation_records = 100/0/0/0/0`，恢复后 `101/1/0/0/0`，增量恰为恢复后那 1 帖 + 1 任务，故障期间打出的两次写请求未留下任何行，「任务无帖子」0 行。本地后端全量 pytest **578 passed / 0 failed**（隔离 PG/Redis 实跑），迁移链与 API 契约由 **Production CI** 判定。数值、命令原文见 `docs/production/verification.md` 的「G2 可靠性：PostgreSQL 不可达时写路径错误码修复复测（2026-11-04）」小节。

- **[优先级: 高] [已完成 2026-11-04]** API 契约的接口面没有硬门禁（导出契约覆盖入库快照、从不与之比对）

  - 当前影响：仓库文档一直把「接口面不得变化、契约 paths 数保持不变（132 paths）」当成既定不变量（`.agent/dispatch-queue.json` 每条历史都写着「API 契约 132 paths 不变」，`docs/production/release-gates.md` 的发布审核段要求「后端、Web、管理端版本组合与上一版兼容」），但**仓库里没有任何守卫在守它**：`scripts/check_api_contract.py` 只校验必备端点存在、路径带 `/api/v1/` 版本前缀、响应 schema 里没有密钥字段，随后就把导出的契约**写回** `release/openapi.json` —— 它覆盖了入库快照、从不与快照比对。于是后端加一条或删一条接口路径时 CI 照样全绿，接口面的静默漂移没有任何门禁能发现，前端与管理台的契约守卫（`frontend/scripts/api-contract-check.mjs`）也跟着一起漂移。
  - 建议方案：在 `scripts/check_api_contract.py` 里加一条与入库快照 `release/openapi.json` 的比对断言 —— 导出的 **paths 集合**、**每个路径的方法集合**与**路径数**必须与快照逐条一致，任何增删都立刻失败；比对放在写文件之前，失败时既不写出契约文件也不改写入库快照；路径数不写死成常量，一律以入库快照为准；并按仓库既有做法在 `scripts/tests/` 下加守卫用例，随 CI 运维脚本回归一起跑。
  - 验证方式：`python scripts/check_api_contract.py --output release/openapi.json` 退出码 0 并打印契约路径数（与入库快照逐条一致）；守卫用例随运维脚本回归全绿；负向验证（把入库快照临时改成少一条路径）必须退出码非 0 并逐条指出差异；Production CI 的 `verify` 作业复跑确认契约导出步骤与后端全量 pytest 均通过、契约 paths 数不变。
  - 已完成（2026-11-04）：① `scripts/check_api_contract.py` 新增与入库快照的比对（`compare_with_snapshot()`：路径集合、每个路径的方法集合、路径数逐条一致，差异逐条列出并非零退出），比对在写文件之前完成，失败时既不写出契约文件也不改写入库快照；后端导入改为函数内延迟导入（`load_contract()`）以便守卫脚本可被单元测试直接调用；另加 `--update-snapshot`（**只有显式带上、且 `--output` 指向入库快照时**才跳过比对并刷新快照）作为有意变更接口面时的唯一出口。② 新增守卫用例 `scripts/tests/test_api_contract_snapshot_guard.py`（**7 项**）随 CI 运维脚本回归一起跑：锁住「比对确实存在」「打印的路径数与入库快照一致且脚本里没有写死的路径数常量」「新增路径 / 删除路径 / 方法集合变化时退出码非 0 且快照未被改写」「`--update-snapshot` 的两条行为」。**本地实测**：契约导出退出码 0、打印 `contract validated: 132 paths`（写回后与入库快照逐字节一致）；负向验证退出码 1 并报 `added paths: /api/v1/posts/hot` 与 `path count: snapshot 131, exported 132`；运维脚本回归 **81 项全绿**。未改后端接口、未改 `release/openapi.json` 的内容、未改发布门禁口径；后端全量 pytest 与契约导出步骤仍以 Production CI 的 `verify` 作业为权威判定。

- **[优先级: 高] [已完成 2026-11-04]** 任务队列信号既没有可抓取的指标、也没有告警规则（runbook 的 jobs 告警目标落空）

  - 当前影响：`docs/production/runbook.md` 的「首发告警目标」表把 jobs 列为首发告警目标（最老 pending>10 分钟持续 5 分钟、dead>0、running 租约过期），并明确写着「任务、主机、DB、备份指标需要接入对应exporter或应用metrics并验证」「不得把表中目标说成所有告警已经配置」。但改动前：① 应用 `/metrics` 只暴露 HTTP 请求计数与时延直方图，**没有任何任务队列信号**，Prometheus 抓不到待处理数、最老待处理任务年龄、死信数与租约过期的运行中任务数；② `deploy/monitoring/alerts.yml` 只覆盖探针与 HTTP RED（SchoolWallUnavailable / ProbeSlow / CertificateExpiring / MonitorTargetMissing / ApiErrors / ApiSlow），**没有任何一条针对 jobs 的规则**。结果是 runbook 表里的 jobs 目标既没有指标也没有规则 —— 值班人收不到「待审任务积压 / 死信」告警。更糟的是这类空转没有任何门禁能发现：规则文件里写一个谁都没暴露的指标名，CI 照样全绿。
  - 建议方案：① 在应用 `/metrics` 暴露四个任务队列信号（待处理数、最老待处理任务等待秒数、死信数、租约过期的运行中任务数），采集只跑一条聚合 SQL、只输出计数与时长，**不带 payload、证件、token 或用户内容**；最老待处理任务按**入队时间**算（退避重排只推迟下一次可执行时间，不会让积压从视野里消失），口径与 `docs/production/capacity.md` 的「待审任务最旧年龄」一致；数据库不可用时采集失败只把 collection_ok 置 0、不抛异常，避免一次数据库故障把 RED 指标一起抹掉。② 在 `deploy/monitoring/alerts.yml` 按 runbook 表补三条规则，阈值与 `for` 时长照抄该表（表内没给持续时长的两项按立即触发处理）。③ 新增守卫脚本与守卫用例，断言每条规则表达式引用的指标都真实可抓取（应用 `/metrics` 实际输出的指标名，或 blackbox/`up` 等既定 exporter 指标名），防止规则引用无人暴露的指标而空转。
  - 验证方式：`/metrics` 实测输出含四个新指标且数值与库内任务状态一致（改动前对照：`schoolwall_jobs_*` 指标 0 条）；守卫脚本退出码 0，负向验证（规则里放一个没人暴露的指标名）必须非零退出并点名该指标；守卫用例随 CI 运维脚本回归全绿；Production CI 的 `verify` 作业（后端全量 pytest + 运维脚本回归）全绿；API 契约 paths 数保持 132 不变（`/metrics` 不在契约里）。
  - 已完成（2026-11-04）：① 新增 `backend/app/metrics.py` 作为应用的指标面（HTTP RED 两个指标一并迁入），新增 `schoolwall_jobs_pending` / `schoolwall_jobs_oldest_pending_age_seconds` / `schoolwall_jobs_dead` / `schoolwall_jobs_running_lease_expired` 与 `schoolwall_jobs_metrics_collection_ok`；`backend/app/main.py` 的 `/metrics` 在渲染前顺带刷新队列信号。② `deploy/monitoring/alerts.yml` 补 `SchoolWallJobsBacklog`（`> 600`，`for: 5m`）、`SchoolWallJobsDeadLetters`（`> 0`，立即）、`SchoolWallJobsLeaseExpired`（`> 0`，立即），阈值与持续时长照抄 runbook 表。③ 新增 `scripts/check_monitoring_alerts.py` 与守卫用例 `scripts/tests/test_monitoring_alerts.py`（**6 项**），随 CI 运维脚本回归一起跑。**本地实测**（专用隔离环境：容器化 PostgreSQL 15.14 / Redis 7.4.7）：改动前后对照抓取同一 `/metrics` —— 改动前 `schoolwall_jobs_*` **0 条**，改动后 `schoolwall_jobs_pending 1.0`、`schoolwall_jobs_oldest_pending_age_seconds 1203.870003`、`schoolwall_jobs_dead 1.0`、`schoolwall_jobs_running_lease_expired 0.0`、`schoolwall_jobs_metrics_collection_ok 1.0`；后端用例 `backend/tests/test_job_metrics.py` **2 passed**（含「数据库不可达时 /metrics 仍 200 且 RED 指标仍在」「任务 payload 不进指标」）；守卫脚本退出码 0 并打印 `monitoring alerts validated: 9 rules, all referenced metrics are scrapeable (29 known metric names)`，负向验证非零退出并点名指标；运维脚本回归 **87 项全绿**；API 契约 **132 paths** 不变。未改发布门禁口径、未改告警接收端；主机/DB/备份类信号仍需对应 exporter，保持为已记录的缺口。数值与命令原文见 `docs/production/verification.md` 的「G2 可靠性：任务队列信号接成可抓取的应用指标与告警规则（2026-11-04）」小节。

- **[优先级: 高] [已完成 2026-11-04]** DB/Redis 的应用侧信号既没有可抓取的指标、也没有告警规则（runbook 的 DB/Redis 告警目标落空）

  - 当前影响：`docs/production/runbook.md` 的「首发告警目标」表把 DB/Redis 列为首发告警目标（pool使用>80% 持续 10 分钟、锁等待上升、Redis失败>0），处理列是「查慢SQL/连接预算，禁止盲目加worker」，并要求「不得把表中目标说成所有告警已经配置」。但改动前：① 应用 `/metrics` 只暴露 HTTP RED 与（上一轮补的）任务队列信号，**没有连接池用量、也没有 Redis 失败计数**；② `deploy/monitoring/alerts.yml` 只有探针、HTTP RED 与 jobs 三条规则，**没有任何一条针对 DB/Redis 的规则**。与 jobs 行同样的空转：表里写了目标，既没有可抓取的指标也没有规则，值班人收不到「连接池打满 / Redis 故障」告警。
  - 建议方案：① 在应用 `/metrics` 暴露 DB/Redis 的应用侧信号 —— 数据库连接池的已用连接数、溢出连接数、连接预算（`DB_POOL_SIZE + DB_MAX_OVERFLOW`，与 runbook「数据库连接总预算」口径一致）与使用率比率，以及 Redis 调用失败计数；采集只输出计数、时长与比率，**不带连接串、口令、键名、payload 或任何用户内容**；连接池状态取自进程内、不查库，数据库变慢或不可达时依然可读。② 在 `deploy/monitoring/alerts.yml` 按 runbook 表补两条规则（使用率 >80% 持续 10 分钟、Redis 失败 > 0），阈值与 `for` 时长照抄该表；Redis 失败用 `increase(...[5m])` 判定 —— 计数只增不减，直接写 `> 0` 会让规则一直挂着、再也不恢复。③ 扩展守卫口径：除「引用了没人暴露的指标」，新增「一个指标都没引用的规则」（恒真/恒假）同样拦下，并锁住 DB/Redis 规则的阈值与持续时长照抄 runbook 表。
  - 验证方式：`/metrics` 实测输出含新增的 DB/Redis 指标；Redis 不可达时失败计数真的增长且错误码语义不变（503）；守卫脚本退出码 0，负向验证（规则里放一个没人暴露的指标名、或一条不引用任何指标的规则）必须非零退出；守卫用例随 CI 运维脚本回归全绿；Production CI 的 `verify` 作业（后端全量 pytest + 运维脚本回归）全绿；API 契约 paths 数保持 132 不变（`/metrics` 不在契约里）。
  - 已完成（2026-11-04）：① `backend/app/metrics.py` 新增 `schoolwall_db_pool_used_connections` / `schoolwall_db_pool_overflow_connections` / `schoolwall_db_pool_max_connections` / `schoolwall_db_pool_usage_ratio` 与 `schoolwall_redis_failures_total`；`backend/app/utils/redis.py` 的 `redis_client` 改为 `InstrumentedRedis` 代理（调用失败计一次数、异常照旧上抛；redis-py 5.x 的异步命令方法返回协程，故同步抛出与协程 await 抛出都算失败），`backend/app/main.py` 的 `/metrics` 在渲染前刷新连接池指标。② `deploy/monitoring/alerts.yml` 补 `SchoolWallDbPoolPressure`（`schoolwall_db_pool_usage_ratio > 0.8`，`for: 10m`）与 `SchoolWallRedisFailures`（`increase(schoolwall_redis_failures_total[5m]) > 0`，立即触发），阈值与持续时长照抄 runbook 表。③ `scripts/check_monitoring_alerts.py` 新增「规则必须至少引用一个可抓取指标」的检查，`scripts/tests/test_monitoring_alerts.py` 扩到 **10 项**（新增 4 项：DB/Redis 指标可抓取、DB/Redis 规则阈值照抄 runbook、DB/Redis 规则只用应用暴露的指标、无指标引用的规则被拦下），随 CI 运维脚本回归一起跑。**本地实测**（专用隔离环境：容器化 PostgreSQL 15.14 / Redis 7.4.7）：真实 `/metrics` 抓取到 `schoolwall_db_pool_used_connections 0.0` / `schoolwall_db_pool_overflow_connections 0.0` / `schoolwall_db_pool_max_connections 15.0` / `schoolwall_db_pool_usage_ratio 0.0` / `schoolwall_redis_failures_total 0.0`；另一份指向不可达 Redis 的 API 上 `/health/ready` **503**、`/health/live` **200**（语义未变），失败计数随每次失败的 Redis 调用递增（2.0 → 3.0），带限流校验的登录请求仍返回 **503**「安全校验服务暂时不可用，请稍后重试」；后端用例 `backend/tests/test_db_redis_metrics.py` **8 passed**、后端全量 pytest **585 passed**（3 项教务真实链路 E2E 因本机无外网被排除，CI 无 `.env` 时自动跳过）；守卫脚本退出码 0 并打印 `monitoring alerts validated: 11 rules, all referenced metrics are scrapeable (36 known metric names)`，负向验证非零退出并点名；运维脚本回归 **91 项全绿**；API 契约 **132 paths** 不变。未改发布门禁口径、未改告警接收端；**DB 锁等待上升**与主机容量、备份类信号仍需对应 exporter（postgres_exporter / node_exporter 等），保持为已记录的缺口。数值与命令原文见 `docs/production/verification.md` 的「G2 可靠性：DB/Redis 应用侧信号接成可抓取的应用指标与告警规则（2026-11-04）」小节。

- **[优先级: 高] [已完成 2026-11-04]** 备份侧信号既没有可抓取的指标、也没有告警规则（runbook 的备份告警目标落空）

  - 当前影响：`docs/production/runbook.md` 的「首发告警目标」表把备份列为首发告警目标（WAL归档>30分钟或失败增长、最新备份>26小时），处理列是「立即修复备份；未恢复保护前停止新增风险变更」，并要求「不得把表中目标说成所有告警已经配置」。但改动前：① 仓库自控的逻辑备份（`deploy/backup.sh`）跑完只在磁盘上留一份 `.sql.gz`，**没有任何可抓取的信号** —— 备份是多久以前的、刚刚那次成功没有、失败了几次，应用与 Prometheus 都看不到；② `deploy/monitoring/alerts.yml` 只有探针、HTTP RED、jobs 三条与 DB/Redis 两条，**没有任何一条针对备份的规则**。与 jobs 行、DB/Redis 行同样的空转：值班人收不到「备份过期 / 备份失败」告警。
  - 建议方案：① 把仓库自控的备份侧信号接成可抓取的指标 —— `deploy/backup.sh` 每次尝试（成功或失败）都把结果写进状态文件 `backup_status.json`（`deploy/backup_status.py` 维护，**只有时间戳与计数，不含备份路径、对象存储密钥、连接串或备份内容**），应用 `/metrics` 读同一个文件，暴露「距最近一次成功备份的秒数」「最近一次尝试是否成功」「失败次数」「状态是否读到了」四个信号（计数、时长与布尔）；状态读不到时按未知记（`-1`）并把 `collection_ok` 置 0，**不抛异常** —— `/metrics` 是抓取入口，不能因为备份状态读不到就整个 500。生产把状态目录以只读方式挂进后端容器（compose 的 `BACKUP_STATUS_DIR`）。② 在 `deploy/monitoring/alerts.yml` 按 runbook 备份行接上规则：`SchoolWallBackupStale`（最新备份 >26 小时，即 >93600 秒）、`SchoolWallBackupFailed`（最近一次备份未成功，或失败计数在增长）、`SchoolWallBackupStatusUnknown`（状态读不到 —— 信号没接上时必须让人看见，不能静默）；表内没给持续时长，按立即触发处理。③ 扩展守卫口径：新增规则引用的指标同样必须真实可抓取，守卫用例锁住备份规则的阈值照抄 runbook 备份行，并**断言仓库不得冒充已覆盖 WAL 归档**（pgBackRest 侧仍属人工与基础设施安排）。
  - 验证方式：`/metrics` 实测输出含四个备份信号且数值随状态文件变化（成功 → 年龄变小、失败 → 布尔变 0、失败数增长 → 计数递增）；状态文件缺失或损坏时 `/metrics` 仍 200 且按未知暴露；守卫脚本退出码 0，负向验证（规则里放一个没人暴露的指标名）必须非零退出；守卫用例随 CI 运维脚本回归全绿；Production CI 的 `verify` 作业（后端全量 pytest + 运维脚本回归）全绿；API 契约 paths 数保持 132 不变（`/metrics` 不在契约里）。
  - 已完成（2026-11-04）：① 新增 `deploy/backup_status.py`（写状态文件，原子写、目录 0755 / 文件 0644 以便被后端容器 uid 10001 只读读到）与 `backend/app/backup_status.py`（只读解析）；`deploy/backup.sh` 成功与失败两条路径都会写状态（失败时用 EXIT trap 记，写状态失败只打印一行告警，不把成功的备份判成失败）；`backend/app/metrics.py` 新增 `schoolwall_backup_last_success_age_seconds` / `schoolwall_backup_last_attempt_succeeded` / `schoolwall_backup_failures_total` / `schoolwall_backup_status_collection_ok`，`backend/app/main.py` 的 `/metrics` 在渲染前刷新（`/metrics` 不在接口契约里，路径数不变）；`deploy/docker-compose.prod.yml` 以只读方式挂载 `${BACKUP_STATUS_DIR:-/opt/schoolwall/backup-status}:/data/backup-status:ro` 并把 `BACKUP_STATUS_FILE` 指向容器内路径。② `deploy/monitoring/alerts.yml` 补三条规则（阈值与持续时长照抄 runbook 备份行）。③ `scripts/tests/test_monitoring_alerts.py` 扩到 **14 项**（新增 4 项：备份指标可抓取、备份规则阈值照抄 runbook 备份行、备份规则只用应用暴露的指标、不得冒充已覆盖 WAL 归档），`scripts/tests/test_backup_script.py` 扩到 **5 项**（新增 3 项：成功与失败都写状态、状态文件对后端容器可读），随 CI 运维脚本回归一起跑。**本地实测**（专用隔离环境：容器化 PostgreSQL 15.14 / Redis 7.4.7）：真实 `/metrics` 抓取到 `schoolwall_backup_last_success_age_seconds 20.477206` / `schoolwall_backup_last_attempt_succeeded 1.0` / `schoolwall_backup_failures_total 0.0` / `schoolwall_backup_status_collection_ok 1.0`；随后把状态文件改成一次失败再抓取 → `schoolwall_backup_last_attempt_succeeded 0.0`、`schoolwall_backup_failures_total 1.0`（失败数增长才递增）；后端用例 `backend/tests/test_backup_metrics.py` **6 passed**、后端全量 pytest **594 passed**（121.22 秒）；守卫脚本退出码 0 并打印 `monitoring alerts validated: 14 rules, all referenced metrics are scrapeable (42 known metric names)`；运维脚本回归 **98 项全绿**；API 契约导出退出码 0 并打印 `contract validated: 132 paths`（写回后与入库快照逐字节一致）。未改发布门禁口径、未改告警接收端；**WAL 归档/PITR、异机备份与备份加密仍需 pgBackRest 与人工安排，保持为已记录的缺口**。数值与命令原文见 `docs/production/verification.md` 的「G2 可靠性：备份侧信号接成可抓取的应用指标与告警规则（2026-11-04）」小节。
