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

  - 当前影响（2026-11-02 更新）：后端 pytest 已在目标 PostgreSQL 15 + Redis 7 上跑通（Production CI 运行 41369377491 的 verify 作业：**535 passed / 3 skipped**，运维脚本回归 20 项全 ok），迁移 `529bf8becb3f`、`b7e2c4a91d30` 的 upgrade → downgrade → 再 upgrade 与 `alembic check` 亦在同一环境通过，逻辑恢复冒烟通过，契约导出 125 paths，`pip-audit --strict` 无已知漏洞；密钥扫描（Gitleaks）通过。**镜像 Trivy 扫描实跑并失败** —— 基础镜像 `python:3.11-slim`（Debian 13.7）自带 46 条无修复版本 HIGH，另有镜像内 `setuptools` 内置依赖 2 条 HIGH，扫描失败即中止推送（带高危的镜像未发布）。仍未取得：k6 容量门禁（G3：100req/s×30min、200req/s×5min、8h soak）无数值、异机备份/PITR 与告警演练、独立人工安全复核。**发布门禁 G1（镜像扫描零未豁免高危）/G2（真实恢复与告警）/G3 因此仍未解除。**
  - 建议方案：按 `docs/production/capacity.md` 建隔离库跑种子与 k6；镜像侧分两步 —— ① 仓库自控部分：在 `backend/Dockerfile` 内清理镜像自带的 `setuptools` 内置依赖（`jaraco.context`、`wheel` 两条 HIGH 有修复版本）；② 基础镜像的 46 条 HIGH 在 Debian 13 尚无修复版本，只能等上游发布安全更新后重建，或改用不含 `util-linux`/`ncurses`/`perl-base`/`libsystemd0` 的镜像族 —— 后者属基础镜像族级变更，须走 `openspec/changes/` 提案与人工决策。独立安全复核需人工安排。
  - 验证方式：按 `docs/production/release-gates.md` 逐门禁保存提交、日期、环境、执行人、命令与原始报告，无证据一律保持未通过；镜像侧以 Production CI main 分支 image 作业的 Trivy 步骤退出码 0（0 HIGH / 0 CRITICAL）且导入冒烟仍打印 `built image imports and exports contract` 为准。
