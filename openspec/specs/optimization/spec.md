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
  - 已完成：改用 `unplugin-vue-components` + `unplugin-auto-import` 的 `ElementPlusResolver` 按需引入，CSS 同步按需。locale 由 `app.use(ElementPlus, {locale})` 改为 `provideGlobalConfig({ locale: zhCn }, app)`（不注册全部组件的前提下仍提供中文 locale，已实测 MessageBox 按钮为「取消/确定」）。**实测首屏 411KB → 98KB gzip（-76%）、1458KB → 268KB raw（-82%）；主 chunk 1099KB → 255KB raw；CSS 359KB → 19KB。**
  - 踩坑（务必留意）：① Element Plus 按需注入的组件样式会在 `main.ts` 的样式 import **之后**进入产物，同特异性下后加载者胜，Element Plus 默认蓝（#409eff）会反过来盖掉玫瑰红，导致全视图走查 34/34 全挂（按钮变默认蓝、文字对比度掉到 2.0~3.1:1）。解法：`theme.css` 的选择器提到 `html:root`（0,1,1 > `:root` 0,1,0）与 `html.dark:root`（0,2,1 > `html.dark` 0,1,1），与注入顺序解耦。② `el-table` 的 slot 行类型固定为 `DefaultRow`，组件一旦被 `components.d.ts` 声明出真实类型，原先被 `any` 掩盖的 42 处类型不匹配全部暴露；已在模板里用 `row as X` 标注，并把 el-tag 的状态映射表标注为 `TagProps['type']`。③ `unplugin-*` 生成的 dts 必须**提交入库**，否则 CI 里先跑的类型检查拿不到声明；且 `build` 脚本改为 `vite build && vue-tsc --noEmit`（先出 dts 再校验），避免「类型报错 → 构建不执行 → dts 不更新」的死锁。
  - 验证方式：构建后比对 `dist/assets/index-*.js` 与 `index-*.css` 的 gzip 体积；跑 `admin-frontend/scripts/all-views-walkthrough.py`（34/34）确认 41 种组件仍全部挂载且主题色未被覆盖。

- **[优先级: 高]** 管理台 echarts 整包懒加载块 372KB gzip

  - 当前影响：`DashboardView.vue` 用 `import('echarts')` 动态加载，已做到不进首屏；但整包 1.1MB raw，打开看板即下载 372KB gzip。
  - 建议方案：换 `echarts/core` + 按需注册图表与组件（`BarChart` / `LineChart` / `PieChart` + `GridComponent` / `TooltipComponent` / `LegendComponent` + 需要的 renderer），预计降到 150~200KB gzip。
  - 验证方式：构建后看懒加载 chunk 的 gzip 体积；跑 `admin-frontend/scripts/dashboard-walkthrough.py` 确认图表仍渲染、图例与坐标轴文字取主题色。

- **[优先级: 中]** 前端性能基线未入库、无回归门禁

  - 当前影响：`frontend/scripts/ui-perf-audit.py` 把首屏指标写到 `/tmp/audit/metrics.json`，不入库、不比阈值。性能是否退化目前没有任何自动判定，只能靠人肉看。
  - 建议方案：把基线 JSON 提交到 `release/`，脚本加阈值比对（首屏 JS 总量、LCP/DOMContentLoaded 预算），超阈值即非零退出；接进 CI 的「Objective UI defect audit」步骤同批执行。
  - 验证方式：连续两次跑结果落在基线 ±5% 内；人为放大一个阈值即失败。

- **[优先级: 中]** 图标「注册表唯一来源」名存实亡，103 个 SVG 无人引用

  - 当前影响：`openspec/specs/frontend-ui/spec.md` 要求「一律通过 `utils/icons.ts` 注册表引用，不得手写路径」，实际 91 处源码直接写死 `<image src="/static/icons/...">`，只有底栏走注册表；207 个 SVG 里 103 个（29KB）没有任何地方引用。生成器作为「几何唯一来源」的实际约束力不足，换色与清理都要靠人工核对。
  - 建议方案：二选一 —— ① 把页面改成经 `UiIcon` / 注册表取路径（工作量中等，但能真正做到一处生成、全局生效）；② 或修正规范措辞为「注册表负责语义名与变体选择，路径由生成器产出」，并加一个「磁盘文件 ↔ 注册表 ↔ 引用」三者一致的静态检查，同时清掉无人引用的 SVG。
  - 验证方式：加静态检查脚本，断言注册表与磁盘文件一一对应、无零引用文件；跑 `frontend/scripts/ui-contrast-audit.py` 与全页面走查确认无坏图。

- **[优先级: 低]** 残余 moderate 依赖告警（构建期，不进产物）

  - 当前影响：主前端 20 moderate（`@intlify/core-base` 两条 advisory），管理台 3 moderate（`vue-tsc` → `@vue/language-core` → `minimatch` globparts 放大 ReDoS，GHSA-g3hv-75wg-m249）。均为 devDependency 传递链，实测客户端产物中不含相关代码，**0 high / 0 critical**。
  - 建议方案：主前端等 uni-cli-shared 的 `@intlify` 锁定版本推进（9.x 线内无同时避开两条 advisory 的版本，跨大版本会破坏其对 `@intlify/runtime@9.1.9` 的精确锁定）；管理台等 `@vue/language-core` 跟进 `minimatch >= 11.0.1`。**不要用 `overrides` 强行覆盖**，会破坏类型工具链。
  - 验证方式：每次升级后重跑 `npm audit --registry=https://registry.npmjs.org --audit-level=high`，并实测产物不含告警包字样。

- **[优先级: 低]** 前端 7 套走查脚本仍各带一份静态服务代码

  - 当前影响：`frontend/scripts/` 下 7 个脚本各自定义了一份几乎相同的 `SilentHandler`/`QuietHandler`（H5 用 hash 路由，不需要 SPA 回退，所以比管理台那批更简单）。管理台侧已抽出共享模块 `admin-frontend/scripts/walkthrough_server.py`，前端侧尚未跟进。H5 当前部署在根路径（nginx `location /`），**不影响 CI 运行**，故本轮未动。
  - 建议方案：把 `create_server()` 加进已有的 `frontend/scripts/h5_mock_api.py`（前端共享模块），7 个脚本改为 import；顺手把 `web-login-guard-walkthrough.py` 与 `all-pages-walkthrough.py` 各自内嵌的 mock 也归入共享模块。
  - 验证方式：7 套脚本改后逐个跑通，报告 JSON 与改前一致。

- **[优先级: 高，但需外部环境]** 真实环境验证缺口（工具链已就绪，缺环境）

  - 当前影响：后端 pytest 未在目标 PostgreSQL 15 / Redis 7 跑过；迁移 `529bf8becb3f`、`b7e2c4a91d30` 未实测 upgrade/downgrade；k6 容量门禁（G3：100req/s×30min、200req/s×5min、8h soak）无数值；镜像 Trivy 扫描、真实密钥扫描、独立安全复核均未执行。**发布门禁 G1/G2/G3 因此仍未解除。**
  - 建议方案：按 `docs/production/capacity.md` 建隔离库跑种子与 k6；用 CI 已配置好的 postgres 15 / redis 7 service 跑全量后端用例与迁移链；镜像扫描与 Gitleaks 由 CI 承担并留证；独立安全复核需人工安排。
  - 验证方式：按 `docs/production/release-gates.md` 逐门禁保存提交、日期、环境、执行人、命令与原始报告，无证据一律保持未通过。
