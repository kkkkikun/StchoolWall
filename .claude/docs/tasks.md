# tasks.md — SchoolWall 全局任务追踪

> 最后更新：2026-07-06 ｜ 维护者：开发团队（assistant 按需更新）
> 用途：跨会话的任务总览。OpenSpec 变更级任务在 `openspec/changes/<name>/tasks.md`，本文件做全局聚合与阻塞记录。

---

## 进行中 (In Progress)

> 暂无活跃变更（见已完成）。下一个大方向候选见下方 Backlog。

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
