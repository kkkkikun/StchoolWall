# Tasks: 后端社交互动层

> 优先级 A→B→C→D，按模块分批交付。每批：迁移+实现+pytest 全绿+前端切真实 API+用户验收。
> ⚠️ 前置阻塞：需要 Docker Desktop 运行（起 PG+Redis + 测试库 ey_wall_test），否则无法跑 pytest。

## 前置（已解除）

- [x] P1. 启动 Docker Desktop（Windows），确认 `docker` 可用（原生 docker 28.3.3 + WSL 集成已开）
- [x] P2. `docker compose up -d` 起 PostgreSQL+Redis；创建测试库 `ey_wall_test`
- [x] P3. 跑现有 `python -m pytest` 确认基线全绿 → **111 passed**

## 模块 A · 互动基础（评论/点赞/收藏/足迹 + 计数 + 统计）— ✅ 前后端完成

- [x] A1. Alembic 迁移 `add_interaction_tables`（revision a8f3c2e1b904）：posts 加 like_count/comment_count/view_count；新建 comments/likes/favorites/footprints
- [x] A2. models：Comment / Like / Favorite / Footprint；`models/__init__` 注册
- [x] A3. schemas：CommentCreate
- [x] A4. services/interaction：评论 CRUD（软删）、点赞/收藏幂等 toggle（带计数维护）、足迹记录、stats 聚合
- [x] A5. routers/interaction + posts 增强：评论/点赞/收藏/足迹/me 路由；posts 列表/详情返回计数与 is_liked/is_favorited；详情记足迹+浏览数
- [x] A6. tests/test_interaction（19 用例）：重复点赞幂等、删他人评论 403、计数同步、stats 正确、足迹记录、列表/详情带互动字段
- [x] A7. 验收（后端）：`pytest` 全套 **130 passed**（111 基线 + 19 新增）+ curl 实测点赞/评论/收藏/详情/统计全部 200
- [x] A8. 前端集成（模块 A 前后端全闭合）：
  - ✅ dev-login（后端 development-only + 前端我的页"一键登录"）
  - ✅ post_type 对齐后端；api/posts 防腐映射层；H5 走 vite 代理（修 WSL/CORS）；GET 查询参数过滤空值（修 422）
  - ✅ 首页信息流接真实 GET /posts；feed-card 真实点赞/收藏（乐观更新）
  - ✅ 我的页接真实 /me/stats
  - ✅ post-detail 重写：真实详情 + 评论列表/发评论/删自己的评论（评论响应加 user_id）+ 点赞/收藏 + 举报 + 红色化
  - 验证：后端 133+ passed、type-check 0、build:h5 DONE、curl 链路全通（含评论 user_id）

## 模块 B · 发现增强（热帖 + 搜索）— ✅ 前后端完成

- [x] B1. services/post：hot_posts（近 7 天、非广告、like*3+comment*2+view 加权）、search_posts（ILIKE）
- [x] B2. routers：GET /posts/hot、GET /posts/search（在 /{post_id} 之前注册，避免路径冲突）
- [x] B3. tests/test_discover（8 用例）：hot 排序/排除广告/limit/公开、search 命中/无匹配/q 必填/排除广告
- [x] B4. 前端：首页十大热帖接真实 getHotPosts；搜索框 → 新增 pages/search 搜索页接真实 searchPosts；type-check 0
- [x] B5. 验收：后端 141 passed、curl hot(7)/search(1) 通、H5 200

> 分类（金刚区）对齐暂缓：post_type 取值与金刚区 10 项非 1:1，需单独设计分类法，留作后续。

## 模块 C · 消息通知（无 IM）— ✅ 前后端完成

- [x] C1. 迁移 `c2b4f6a8d910_add_notifications` + model Notification
- [x] C2. services/notification：create_notification（不通知自己）、list（未读优先）、unread_summary（4 类，im 恒 0）、mark_all_read、mark_read
- [x] C3. 点赞/评论动作埋点写通知（不通知自己；收藏不通知）
- [x] C4. routers/notification + tests/test_notification（9 用例）
- [x] C5. 前端：消息页 4 角标接 unreadSummary、帖子动态接 listNotifications、全部已读、点通知跳详情+标已读、私信 tab "暂未开放"
- [x] C6. 验收：后端 150 passed、curl 通知列表/全部已读/summary 全通、type-check 0

## 模块 D · 组局·攒局

- [ ] D1. 迁移 `add_party_tables` + models Party/PartyMember
- [ ] D2. services/party：创建/列表/详情/报名/退出/我的局/累计人数
- [ ] D3. routers/party + tests（报名满额、重复报名、退出、权限）
- [ ] D4. 报名触发通知（接 C）
- [ ] D5. 前端：组局页全量接真实 API
- [ ] D6. 验收
