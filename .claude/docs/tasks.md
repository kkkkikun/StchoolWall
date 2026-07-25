# tasks.md — SchoolWall 全局任务追踪

> 最后更新：2026-07-06 ｜ 维护者：开发团队（assistant 按需更新）
> 用途：跨会话的任务总览。OpenSpec 变更级任务在 `openspec/changes/<name>/tasks.md`，本文件做全局聚合与阻塞记录。

---

## 进行中 (In Progress)

### 后端社交互动层 → openspec/changes/backend-social-layer/

- **状态**：✅ 全部 4 模块（A/B/C/D）前后端完成，后端 160 pytest 绿；可 archive
- **已完成**：A 互动 + B 发现 + C 通知 + D 组局（组局/拼单+报名进度+分类+我的局+发起攒局页）
- **预览**：后端 :8000 + H5 :5173 运行中；登录后可发组局/报名/看进度/我的局
- **下一步**：archive 本变更；之后可做分类(金刚区)对齐、真实微信登录、发布页 post_type 对齐等收尾

### 前端 UI/UX 大改造（对齐 ref/ 设计稿）→ openspec/changes/frontend-redesign/

- **状态**：✅ 首期完成 + 已按反馈微调（去签到、首页沉浸式、广告位轮播）；待 archive
- **范围**：5 主 tab 红色品牌主题 + emoji/SVG 图标 + 全 mock 数据
- **待用户决定**：archive 时机；二级页是否统一红色化；其余 tab 是否也改沉浸式

### OpenSpec 规范体系初始化

- **状态**：✅ 完成（5 spec 校验通过）

---

## 待办 (TODO / Backlog)

### 基础设施 / 工具链

- [ ] **CodeGraph 索引**：运行 `codegraph init -i` → `codegraph status` 确认 healthy，加速后续代码探索与 `/opsx:explore`（源码项目推荐）
- [ ] 提交本次 OpenSpec 初始化产物（`openspec/`、`.claude/docs/`、`CLAUDE.md`）—— 注意：禁止把 Claude 列为 git 共同创作者

### 工程质量

- [ ] 前端补测试（当前测试集中在后端 `backend/tests/`，前端无测试体系）
- [ ] CI：后端 `pytest` + 前端 `type-check` 自动化
- [ ] 前端页面与后端 API 的契约校验（可考虑 OpenAPI 自动生成类型）

### 业务（按 SchoolWall.md MVP 蓝图）

- [ ] 评论区（MVP 蓝图提及，未见实现）
- [ ] 举报流程闭环（`models/report.py` 已存在，确认 router/service 是否完整）
- [ ] 内容审核结果回写与帖子可见性联动验证

---

## 阻塞项 (Blocked)

> 当前无。新增阻塞项请记录：现象 / 根因或未知 / 需要谁介入。

---

## 与 openspec/changes/ 同步说明

- **日常小改**：直接改代码 + 更新本文件即可。
- **重大变更**（新模块、改架构、跨多文件）：用 `/opsx:propose "想法"` 创建变更提案，任务清单写在 `openspec/changes/<name>/tasks.md`，本文件在"进行中"区追加一行指针（如 `→ openspec/changes/<name>/`），变更归档后（`/opsx:archive`）从本文件移除。
- **避免重复**：变更级任务细节不抄进本文件，只留指针。
