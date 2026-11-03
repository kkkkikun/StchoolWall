# tasks.md — SchoolWall 全局任务追踪

> 最后更新：2026-11-02 ｜ 维护者：开发团队（assistant 按需更新）
> 用途：跨会话的任务总览。OpenSpec 变更级任务在 `openspec/changes/<name>/tasks.md`，本文件做全局聚合与阻塞记录。

---

## 进行中 (In Progress)

### 生产化与Web/微信/Android（2026-10-16用户已批准）

- 活跃变更：openspec/changes/production-multiplatform/
- 代码：统一身份/会话/撤销/找回、私有证件人工核验、隔离媒体、持久任务、人工治理、发布与恢复工具
- 实施状态：docs/production/implementation-status.md；测试证据：docs/production/verification.md
- 2026-10-30 进展：主前端npm audit高危清零（0 high，管理台0 vulnerabilities）；新增学生端全页面(53/53)与管理台全视图(34/34) Playwright走查含对比度断言；修复夜间模式文字色、占位符对比度、管理台语义色、图片展示顺序（新增media_assets.position迁移b7e2c4a91d30）
- 发布仍阻断：主体/备案与商店准入、镜像与密钥扫描及独立安全复核、真实COS/审核联调、异机恢复/回滚、容量与三端真机、新增迁移与媒体顺序后端用例尚未在真实PostgreSQL执行（2026-11-02 起，后三项中「迁移与媒体顺序后端用例」已在 Production CI 的 PostgreSQL 15 + Redis 7 环境通过，「密钥扫描」已通过，「镜像扫描」已实跑但失败，见下方 2026-11-02 进展）
- 2026-10-31 进展（主线平台化，feature/main-quality-port）：把主题分支的**非 UI 实现质量**移植回 main —— 后端生产化与 2 个迁移、依赖高危清零、浏览器级走查体系与 2 个永久审计脚本、本地预览服务、统一图标体系（emoji 清零）、语义化令牌、白天/夜晚双模式、管理台补齐三视图；配色沿用 main 玫瑰红品牌。客观扫描 25 页 × 亮/暗全部缺陷归零且品牌例外归零；走查 57/57、16/16、6/6、10/10、11/11、33/33、管理台 34/34 + 8/8 全 PASS；前端单测 55/55（补齐漏带的 5 个测试文件）+ 管理台 12/12（补齐漏带的 1 个）；三端构建通过
- 2026-10-31 已合并入 main（合并点 d7fe503，`--no-ff`）；分支 feature/main-quality-port 保留未删除
- 2026-10-31 改进批次一（CI 守护 + 文档校准）：CI 接入前端+管理台全量单测、openspec 校验、18 套浏览器走查、客观缺陷扫描（actionlint 1.7.7 通过）；修掉管理台走查与 `--base=/admin/` 部署前缀不匹配（曾致 34 场景全挂），抽出共享模块 `admin-frontend/scripts/walkthrough_server.py`；文档三处审计数字与实测对齐；optimization 规范补齐 6 条优化点
- 2026-10-31 改进批次二（管理台体积）：Element Plus 按需引入，首屏 411KB → 102KB gzip（-75%）、raw 1458KB → 303KB（-79%）；locale 改 provideGlobalConfig 保住中文；修掉「默认蓝反盖玫瑰红」「42 处被 any 掩盖的类型错」「服务型样式落错 chunk」「单测绕过自动注入」四个隐藏问题；新增 style-coverage-check.py 样式守卫并接入 CI
- 2026-10-31 改进批次三（性能收口 + 图标单一来源 + 第三方外呼清零）：① echarts 按需注册，懒加载块 1135.53KB → 526.99KB raw、382.15KB → 180.06KB gzip（-53%）；② 性能基线入库 + CI 门禁（学生端 `perf-baseline.json`、管理台 `bundle-baseline.json`，硬门禁只卡确定性体积）；③ 91 处手写图标路径收口到注册表（22 个文件），新增 `icon-consistency-check.py` 静态守卫；④ 前端 7 套走查脚本静态服务去重（新增 `h5_walkthrough_server.py`，backlog 5 → 128）；⑤ **发现并修掉 uni-app 框架的 dcloud CDN 外呼**（每次开页面多一次外网请求，CDN 不可达时走查随机 FAIL），新增 `external-request-check.py` 断言无第三方外呼。CI 步骤 17 → 21
- 2026-11-01 进展（CI 依赖门禁）：pillow 12.3.0 命中 39 条新 advisory，Pillow 13.0.0 要求 Python ≥ 3.11 且 12.3.0 是最后支持 3.10 的版本，按 G1 不得豁免严重/高危，故把后端运行时升到 3.11（CI + 两个 Dockerfile + 版本记录同步），本地已验 pip-audit 通过、app 可导入、图片与证件材料处理行为一致；后端全量与迁移链待 CI 判定
- 剩余待办：真实环境验证缺口（k6 压测、Trivy 镜像扫描零高危、独立安全复核、异机备份/PITR 与告警演练）—— 需外部环境/人工，见 `openspec/specs/optimization/spec.md` 与 `docs/production/release-gates.md`。后端 pytest @PG15+Redis7、迁移 upgrade/downgrade 与 Gitleaks 全量密钥扫描已于 2026-11-02 由 Production CI 取得证据
- 2026-11-01 进展（管理台依赖告警清零）：`vue-tsc` `^2.2.0` → `~3.1.8`，`minimatch` 依赖链消失，管理台官方 npm audit **归零（0 vulnerabilities）**，未用 overrides 强行覆盖；3.2/3.3 线对本仓库模板误报（属性值含 `//`、`:initial-index` 索引类型），故锁 3.1.x。复验：type-check 0 错、单测 12/12、build:admin 通过、样式/体积守卫通过、全视图走查 34/34 PASS。主前端 20 moderate 仍等上游
- 2026-11-02 进展（前端审计原始报告刷新）：`release/frontend-audit*.json` 入库版本已过时（全量那份停在 17 moderate），在 `frontend/` 下用官方 `https://registry.npmjs.org` 重跑 `npm audit --json` 与 `npm audit --omit=dev --json` 刷新入库 —— 全量 **0 high / 0 critical、20 moderate**（17 条 `@intlify/core-base` 链 + 3 条 `openapi-typescript` → `@redocly/openapi-core` → `minimatch` 链），`--omit=dev` **0 high / 0 critical、16 moderate**（与入库旧版逐字节一致）；`docs/client-release-validation.md` 新增刷新记录小节（日期/命令/registry/环境/基线提交），`docs/production/implementation-status.md` 与 `optimization` 规范数字同步。未升级依赖、未加 overrides、未加忽略配置、未改任何包版本，历史结论不变
- 2026-11-02 进展（Production CI 证据取得）：在 GitHub Actions「Production CI」（`.github/workflows/ci.yml`）的真实运行上取到证据 —— 运行 `41369377491`（push 到 main，提交 `917dd7b`，Python 3.11.17 + `postgres:15-alpine` + `redis:7-alpine`）的 **verify 作业全部步骤全绿**：后端全量 **535 passed / 3 skipped**、运维脚本回归 20 项、迁移链空库 upgrade → downgrade → 再 upgrade 与 `alembic check` PASS、逻辑恢复 PASS、契约导出 **125 paths**、`pip-audit --strict` **No known vulnerabilities found**、Gitleaks 通过、OpenSpec 校验 7/7。**image 作业构建与导入冒烟通过（`built image imports and exports contract`），但 Trivy 扫描失败**：基础镜像 `python:3.11-slim`（Debian 13.7）自带 46 条**无修复版本** HIGH，另有镜像内 `setuptools` 内置依赖 2 条 HIGH（`jaraco.context` 5.3.0 / `wheel` 0.45.1），扫描失败即中止推送 —— 未豁免高危、未加 `.trivyignore`、未下调 severity。据此 `openspec/changes/backend-python-311/tasks.md` 第 8 行（后端门禁）**勾选**，第 9 行（image 作业）**保持未勾选**；命令、日期、环境与原始日志写入 `docs/production/verification.md`，`release-gates.md` 的 G1/G2 与 `implementation-status.md`、`optimization` 规范同步为实测状态
- 2026-11-02 进展（电脑端 Web UI 新增端 `desktop-frontend/`）：面向「用电脑访问校园墙的学生用户」的第三个前端，Vue3 + Vite + TS + Element Plus + Pinia + Router + axios，与管理台同栈，构建 base `/pc/`、同源部署在 `/pc/` 路径下（不新增容器与域名）。一期覆盖读 + 写主链路：信息流（推荐/最新/热门/精华，游标翻页）、帖子详情、评论、搜索、标签、轮播、他人主页、消息通知、注册登录、发帖（图片走 `media_ids`）、点赞收藏关注、改资料与下线设备。认证沿用既有会话体系、**不改后端**：访问令牌只放内存；HTTPS 页面走 `X-Client-Type: web`（刷新令牌在服务端 HttpOnly cookie），纯 HTTP 页面因该 cookie 带 `Secure` 会被浏览器丢弃而自动退化为 `native`（刷新令牌随响应体下发），上线 HTTPS 后无需改代码。界面令牌沿用玫瑰红品牌色并支持亮/暗双模式。CI 已接入 type-check / node --test / build / `npm audit --audit-level=high`，`frontend/scripts/api-contract-check.mjs` 增加 `desktop-frontend/src/api` 扫描目录（本地复验退出码 0），发布制品新增 `web/pc/`。自测：type-check 0 错、单测 17/17 通过、构建产物 752KB（主 chunk 361KB / gzip 132KB）、`openspec validate --specs` 7/7 通过、`openspec validate desktop-web-ui` 通过。待办见 `openspec/changes/desktop-web-ui/tasks.md`（体积预算、Playwright 走查、深色对比度走查、线上验收）
- 2026-11-02 进展（镜像内 setuptools 高危清理）：按派活单 `backlog-007` 只做仓库自控部分 —— `backend/Dockerfile` 的依赖安装层内在**同一层**执行 `pip uninstall --yes setuptools wheel` 并断言 `pip list` 里不再有这两个构建期工具，运行期不需要它们，而基础镜像自带 `setuptools 79.0.1` 的 `_vendor` 内置副本正是 Trivy 报的两条 HIGH（`jaraco.context 5.3.0` → 修复 6.1.0、`wheel 0.45.1` → 修复 0.46.2，已用 `pip download setuptools==79.0.1` 解包逐条核对）。本地已验：临时 venv 内卸载退出码 0 且断言无残留、完整复刻安装层 shell 链退出码 0、阻断 `setuptools`/`pkg_resources` 后 `app.main` 仍导出 125 paths、已装依赖与 `tencentcloud-sdk-python==3.1.188`/`cos-python-sdk-v5==1.9.44` 均不 import `pkg_resources`。**未改** `backend/requirements.txt` 应用依赖版本与业务代码，**未加** `.trivyignore`、**未改** `ignore-unfixed`/severity。本机无 Docker，Trivy 权威证据须由合并后 main 分支 image 作业复跑给出（`Python (python-pkg)` 应为 `Total: 0`）；OS 层 46 条无修复版本 HIGH 属镜像族级变更，需等 Debian 上游安全更新或走 `openspec/changes/` 提案与人工决策，故 `openspec/changes/backend-python-311/tasks.md` 第 9 行**保持未勾选**
- 2026-11-02 进展（内部测试反馈通道 `openspec/changes/feedback-channel/`）：给内部测试人员一条「快速反馈」通道 —— 电脑端与 H5 端各一个入口（电脑端顶栏按钮 + `Ctrl+Shift+F`，H5 首页悬浮按钮 + 设置页入口），提交时可带**截图**与**当时的客户端现场**（页面报错、失败请求、路由、视口、主题、网络、平台）。后端新增 `feedbacks` 表与迁移 `d4e6f8a1b357`、反馈提交/截图上传/我的反馈接口、管理端列表·统计·详情·截图·状态流转接口，以及**通用 Webhook 推送**（`generic`/`feishu`/`wecom` 三种载荷，失败只记日志不影响入库）—— 此前仓库没有任何对外推送通道。截图存**独立私有目录** `private-feedback/`，不进公开媒体体系（`media_assets`），只有管理台鉴权接口能读到，并复用媒体归一化抹掉 EXIF。提交分两步（先建记录拿上传令牌、再逐张传截图），使 H5 的 `uni.uploadFile`（单文件）与电脑端共用同一套接口；免登录提交需内部测试口令（`FEEDBACK_TEST_CODE`，未配置则该路径关闭）。验证：后端反馈用例 15/15（服务器独立测试库实跑）、H5 61/61、管理台 16/16、电脑端 23/23，三端 type-check 0 错与构建通过、契约守卫 132 路径 194 字面量通过、`openspec validate --specs` 7/7。顺带修掉两个仓库级缺陷：① 前端与管理台的 `test` 脚本硬编码测试文件列表，新增测试不会被 CI 执行（已改 `tests/*.test.mjs` 通配）；② 管理台清空备注后保存会保留旧备注（后端改为区分「没传」与「传空」）
- 2026-11-03 进展（电脑端补齐三道门禁）：按 `openspec/specs/optimization/spec.md` 的「电脑端体积预算、浏览器走查与深色对比度未入门禁」条目补齐并接入 Production CI —— ① `desktop-frontend/scripts/bundle-budget-check.py` + 基线 `desktop-frontend/bundle-baseline.json`（按实际产物定，未放宽：主 chunk 370356 B raw / 134576 B gzip、全量产物 713864 B raw，容差 10%，与学生端/管理台同口径）；② `desktop-frontend/scripts/ui-walkthrough.py`（Playwright，19 项断言全 PASS、控制台错误 0 条，base 按 `/pc/` 访问），配套 `walkthrough_server.py`（静态服务 + 前缀剥离）与 `desktop_mock_api.py`（信封格式夹具，无真实用户数据）；③ `desktop-frontend/scripts/ui-contrast-audit.py`（亮/暗两套配色 × 四条关键路径，断言基于 `src/styles/tokens.css` 令牌而非色值，阻断项 0 条）。新增单元测试 `scripts/tests/test_desktop_ci_gates.py`（19 项）随运维脚本回归执行。负向验证：基线调小 30% → exit 1 并指出超出的指标；正文令牌改成低对比度色值 → 对比度门禁 exit 1。**同时记录既有配色差距**（未擅自改设计）：品牌色小字最低 3.22:1（暗色下缺提亮的品牌文字令牌）、弱化文字最低 2.84:1、Element Plus 默认占位符 2.30:1，已写入 `openspec/specs/optimization/spec.md` 待后续条目处理
- 原有未提交UI改动保留；未部署、未代替运营方签署政策或提交平台审核

## 已完成（已归档）

### 后端社交互动层（A/B/C/D）+ 前端重做 → 已归档
- ✅ `frontend-redesign`、`backend-social-layer` 两个 OpenSpec 变更已 archive
- ✅ 主 spec 新增 `backend-social`（9 需求）、`frontend-ui`（8 需求）；7 spec 全绿
- ✅ 4 模块：A 互动 / B 发现 / C 通知 / D 组局，前后端全闭合，后端 160 pytest 绿
- ✅ 收尾对齐：发布页接真实 createPost（版块→post_type）、首页金刚区分类过滤
- 全程提交落库（git log：docs → backend → frontend → D → 归档 → 收尾）

### OpenSpec 规范体系初始化
- ✅ 完成（5 spec 校验通过）

---

## 待办 (TODO / Backlog)

### 基础设施 / 工具链

- [x] **CodeGraph 索引**（2026-11-01：本机 codegraph 1.1.0 可用，`codegraph init -i` 建索引后 `codegraph status` 显示 healthy —— 已索引 364 个文件、6,555 节点、16,716 边。索引是本地产物（`.codegraph/`，约 15MB），**不入库**（已加进 .gitignore），换个工作树需重跑一次该命令）
- [x] 提交本次 OpenSpec 初始化产物（`openspec/`、`.claude/docs/`、`CLAUDE.md`）—— 注意：禁止把 Claude 列为 git 共同创作者（2026-11-01 核对：三处均已入库，`git ls-files` 可见；提交历史里也没有把 Claude 列为共同创作者）

### 工程质量

- [x] 前端补测试（2026-11-01 核对：前端已有测试体系 —— `frontend/tests/` 6 个脚本 55 项全绿，`admin-frontend/tests/` 1 个脚本 12 项全绿，两者均已接入 CI）
- [x] CI：后端 `pytest` + 前端 `type-check` 自动化（2026-09-11：deploy/ci/ 全 Docker 化管线，本地全量绿 425 passed；服务器安装执行待用户 → openspec/changes/server-ci/ T8）
- [x] 前端页面与后端 API 的契约校验（2026-11-01：类型由 openapi-typescript 从后端契约生成，并新增 `frontend/scripts/api-contract-check.mjs` 守卫——生成类型与契约必须一致、学生端与管理台 API 模块里的 138 处路径字面量必须都在后端契约中；已接入 CI，两条负向验证均 exit 1）

### 业务（按 SchoolWall.md MVP 蓝图）

- [x] ~~评论区~~ / ~~举报流程闭环~~（均已实现，见 SNAPSHOT 社交互动层；2026-11-01 核对：`openspec/specs/backend-social/spec.md` 9 条需求在册，后端互动接口与前端页面齐备）
- [x] 内容审核结果回写与帖子可见性联动验证（2026-09-03：本地规则层 + moderation_records 落库，E2E 验证三态分流）

---

## 阻塞项 (Blocked)

> 当前无。新增阻塞项请记录：现象 / 根因或未知 / 需要谁介入。

---

## 与 openspec/changes/ 同步说明

- **日常小改**：直接改代码 + 更新本文件即可。
- **重大变更**（新模块、改架构、跨多文件）：用 `/opsx:propose "想法"` 创建变更提案，任务清单写在 `openspec/changes/<name>/tasks.md`，本文件在"进行中"区追加一行指针（如 `→ openspec/changes/<name>/`），变更归档后（`/opsx:archive`）从本文件移除。
- **避免重复**：变更级任务细节不抄进本文件，只留指针。
