# Proposal: 后端社交互动层（支撑 ref/ 新前端）

## 为什么做

ref/ 新前端（首页/组局/发布/消息/我的）已用 mock 数据落地，但后端仍是原始精简 MVP（只有 posts/auth/upload/tags/admin/report）。前端信息流卡片的赞/评论/收藏、十大热帖、搜索、组局、消息通知、个人统计——**后端全部缺失**。本变更为新前端补齐后端能力。

## 做什么（4 个模块，按用户定优先级 1→2→4→3）

- **模块 A · 互动基础**：评论 / 点赞 / 收藏 / 浏览足迹 + 帖子计数（like_count/comment_count/view_count）+ 个人统计接口。支撑首页信息流卡片交互 + 我的页统计。
- **模块 B · 发现增强**：十大热帖（`/posts/hot`）+ 全文搜索（`/posts/search`）+ 分类（金刚区）对齐。
- **模块 C · 消息通知**：通知表（评论/赞/收藏/组局/举报）+ 未读汇总 + 全部已读。**不做站内 IM/私信**（私信入口前端隐藏，二期）。
- **模块 D · 组局·攒局**：组局/拼单帖 + 报名（joined/total 进度）+ 分类筛选 + 我加入的局 + 累计攒局人数。

## 不做什么（Non-goals）

- ❌ 站内私信 IM（WebSocket/消息存储/未读离线）——用户明确"暂不做私信"
- ❌ 签到/积分（前端已移除签到）
- ❌ AI 协助真实调用（发布页 AI 开关保持 mock）
- ❌ 推送（APNs/微信订阅消息）——本期仅站内通知
- ❌ 评论嵌套楼中楼（MVP 仅平铺 + 可选 @，不做多级嵌套）

## 影响范围

- 后端：新增 models / migrations / services / routers / schemas / tests（`backend/app/`、`backend/alembic/versions/`、`backend/tests/`）
- 前端：逐模块把对应页从 mock 切到真实 API（feed-card 交互、首页热帖/搜索、消息页、组局页、我的统计）
- DB：4 次 Alembic 迁移（每模块一次，可独立回滚）
- 安全：评论/组局内容须经既有异步审核管线（复用 moderation）

## 交付节奏

按模块分批：每模块 = 迁移 + 模型 + service + router + schema + **pytest 全绿** + 前端切真实 API → 用户验收 → 下一模块。

## 回滚方案

- 每模块一次 Alembic 迁移，可 `alembic downgrade -1` 单独回滚。
- 新增表/路由不影响既有 posts/auth 流程；前端切换通过 api/*.ts 封装，失败可回 mock。
- 全部在 `backend/` + `frontend/src/` 内，git 可整体 revert。
