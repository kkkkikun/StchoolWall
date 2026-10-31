# tasks.md — SchoolWall 全局任务追踪

> 最后更新：2026-10-31 ｜ 维护者：开发团队（assistant 按需更新）
> 用途：跨会话的任务总览。OpenSpec 变更级任务在 `openspec/changes/<name>/tasks.md`，本文件做全局聚合与阻塞记录。

---

## 进行中 (In Progress)

### 生产化与Web/微信/Android（2026-10-16用户已批准）

- 活跃变更：openspec/changes/production-multiplatform/
- 代码：统一身份/会话/撤销/找回、私有证件人工核验、隔离媒体、持久任务、人工治理、发布与恢复工具
- 实施状态：docs/production/implementation-status.md；测试证据：docs/production/verification.md
- 2026-10-30 进展：主前端npm audit高危清零（0 high，管理台0 vulnerabilities）；新增学生端全页面(53/53)与管理台全视图(34/34) Playwright走查含对比度断言；修复夜间模式文字色、占位符对比度、管理台语义色、图片展示顺序（新增media_assets.position迁移b7e2c4a91d30）
- 发布仍阻断：主体/备案与商店准入、镜像与密钥扫描及独立安全复核、真实COS/审核联调、异机恢复/回滚、容量与三端真机、新增迁移与媒体顺序后端用例尚未在真实PostgreSQL执行
- 2026-10-31 进展（主线平台化，feature/main-quality-port）：把主题分支的**非 UI 实现质量**移植回 main —— 后端生产化与 2 个迁移、依赖高危清零、浏览器级走查体系与 2 个永久审计脚本、本地预览服务、统一图标体系（emoji 清零）、语义化令牌、白天/夜晚双模式、管理台补齐三视图；配色沿用 main 玫瑰红品牌。客观扫描 25 页 × 亮/暗全部缺陷归零且品牌例外归零；走查 57/57、16/16、6/6、10/10、11/11、33/33、管理台 34/34 + 8/8 全 PASS；前端单测 55/55（补齐漏带的 5 个测试文件）+ 管理台 12/12（补齐漏带的 1 个）；三端构建通过
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

- [ ] **CodeGraph 索引**：运行 `codegraph init -i` → `codegraph status` 确认 healthy，加速后续代码探索与 `/opsx:explore`（源码项目推荐）
- [ ] 提交本次 OpenSpec 初始化产物（`openspec/`、`.claude/docs/`、`CLAUDE.md`）—— 注意：禁止把 Claude 列为 git 共同创作者

### 工程质量

- [ ] 前端补测试（当前测试集中在后端 `backend/tests/`，前端无测试体系）
- [x] CI：后端 `pytest` + 前端 `type-check` 自动化（2026-09-11：deploy/ci/ 全 Docker 化管线，本地全量绿 425 passed；服务器安装执行待用户 → openspec/changes/server-ci/ T8）
- [ ] 前端页面与后端 API 的契约校验（可考虑 OpenAPI 自动生成类型）

### 业务（按 SchoolWall.md MVP 蓝图）

- [ ] ~~评论区~~ / ~~举报流程闭环~~（均已实现，见 SNAPSHOT 社交互动层）
- [x] 内容审核结果回写与帖子可见性联动验证（2026-09-03：本地规则层 + moderation_records 落库，E2E 验证三态分流）

---

## 阻塞项 (Blocked)

> 当前无。新增阻塞项请记录：现象 / 根因或未知 / 需要谁介入。

---

## 与 openspec/changes/ 同步说明

- **日常小改**：直接改代码 + 更新本文件即可。
- **重大变更**（新模块、改架构、跨多文件）：用 `/opsx:propose "想法"` 创建变更提案，任务清单写在 `openspec/changes/<name>/tasks.md`，本文件在"进行中"区追加一行指针（如 `→ openspec/changes/<name>/`），变更归档后（`/opsx:archive`）从本文件移除。
- **避免重复**：变更级任务细节不抄进本文件，只留指针。
