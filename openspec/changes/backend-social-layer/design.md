# Design: 后端社交互动层

> 版本：1.0 ｜ 2026-07-08 ｜ 优先级 A→B→C→D

## 0. 既有约定（新代码须遵循）

- 分层：`routers/`（薄入口，参数+调 service）→ `services/`（业务逻辑，纯 DB 操作）→ `models/` + `schemas/`
- 鉴权：`Depends(get_current_user)` / `Depends(get_optional_user)` / `Depends(require_role("student","admin"))`（见 `dependencies.py`）
- 响应格式：`{"code": 0, "data": ..., "message"?: ...}`
- 游标分页：`cursor: int | None`，返回 `items + next_cursor + has_more`
- 安全红线：`real_name` 不进响应；密码不落库
- 测试：`backend/tests/`，独立库 `ey_wall_test`，NullPool，每测试 TRUNCATE（conftest），复用 `guest/student/admin_user` + 对应 token fixtures
- 命名：snake_case，布尔 `is_*`，计数 `*_count`

---

## 模块 A · 互动基础（最先做，详细）

### A.1 数据模型（新增迁移 `add_interaction_tables`）

```
posts 增列：like_count INT DEFAULT 0
           comment_count INT DEFAULT 0
           view_count INT DEFAULT 0     -- 顺带补齐前端 PostDetail 已声明但缺失的字段

comments
  id BIGINT PK
  post_id BIGINT FK→posts.id  (index)
  user_id UUID FK→users.id    (index)
  content TEXT
  status SMALLINT DEFAULT 1   -- 1正常 -1删除
  created_at TIMESTAMPTZ

likes
  user_id UUID FK→users.id
  post_id BIGINT FK→posts.id
  created_at TIMESTAMPTZ
  PK(user_id, post_id)         -- 唯一约束，防重复赞

favorites
  user_id UUID FK→users.id
  post_id BIGINT FK→posts.id
  created_at TIMESTAMPTZ
  PK(user_id, post_id)

footprints
  id BIGINT PK
  user_id UUID FK→users.id     (index)
  post_id BIGINT FK→posts.id
  viewed_at TIMESTAMPTZ DEFAULT now()
  INDEX(user_id, viewed_at DESC)  -- 我的足迹按时间倒序
```

### A.2 计数维护

- 点赞/取消、评论新增/删除：**同步更新** `posts.like_count/comment_count`（事务内 `UPDATE ... SET count = count ± 1`）。MVP 不做异步计数聚合（量级够用）。
- 详情浏览：`GET /posts/{id}` 时 `view_count += 1`（仅已认证用户，防刷：同一用户短时去重可选，MVP 先简单 +1）。

### A.3 API（prefix `/api/v1`）

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/posts` | optional | 列表项**新增** like_count/comment_count/is_liked/is_favorited（当前用户视角） |
| GET | `/posts/{id}` | optional | 详情**新增** 同上 + view_count |
| POST | `/posts/{id}/comments` | student/admin | 发评论 → comment_count+1 → 触发通知 |
| GET | `/posts/{id}/comments` | optional | 评论列表（游标分页，按时间） |
| DELETE | `/comments/{id}` | student/admin(本人) | 删自己的评论 → comment_count-1 |
| POST | `/posts/{id}/like` | student/admin | 点赞（幂等：已赞则不变）→ like_count+1 → 通知 |
| DELETE | `/posts/{id}/like` | student/admin | 取消赞 → like_count-1 |
| POST | `/posts/{id}/favorite` | student/admin | 收藏 |
| DELETE | `/posts/{id}/favorite` | student/admin | 取消收藏 |
| GET | `/me/favorites` | student/admin | 我的收藏（游标分页） |
| GET | `/me/footprints` | student/admin | 我的足迹（游标分页） |
| GET | `/me/stats` | student/admin | {posts_count, comments_count, favorites_count, footprints_count} |

### A.4 前端切换

- `api/interaction.ts`（新）：封装上述接口
- feed-card：赞/收藏按钮接真实 toggle，显示真实计数
- post-detail：评论列表 + 发评论，浏览即记录足迹
- mine：4 列统计接 `/me/stats`，"帖子"跳 my-posts，"收藏/足迹"接新列表页

---

## 模块 B · 发现增强

- `GET /posts/hot?limit=10`：近 7 天按 `like_count*3 + comment_count*2 + view_count` 加权倒序，去广告。前端"十大热帖"。
- `GET /posts/search?q=&cursor=`：PostgreSQL `content ILIKE '%q%'`（MVP），或建 `tsvector` 索引（二期优化）。前端搜索框。
- 分类对齐：`post_type` 现为 seek/secondhand/lostfound/advertisement；前端金刚区是更细分类。方案：复用 `tags` 作为分类，新增 `GET /categories`（聚合 tag + 计数），金刚区点击 → `GET /posts?tag=...`。（细节到 B 模块再定）

---

## 模块 C · 消息通知（无 IM）

```
notifications
  id BIGINT PK
  user_id UUID FK→users.id      (接收者, index)
  actor_id UUID FK→users.id      (触发者)
  type VARCHAR(20)               -- comment/like/favorite/group/report
  post_id BIGINT NULL
  comment_id BIGINT NULL
  is_read BOOLEAN DEFAULT false  (index)
  created_at TIMESTAMPTZ
```

- 触发点：模块 A 的点赞/评论/收藏 → 写一条 notification（不通知自己）。
- `GET /notifications/unread-summary` → `{comment, like, group, im}`（消息页 4 圆角标；im 恒 0）
- `GET /notifications?type=&cursor=` → 列表
- `POST /notifications/read-all`、`POST /notifications/{id}/read`
- 前端消息页：4 类角标 + 帖子动态列表接真实通知；私信 tab 显示"暂未开放"。

---

## 模块 D · 组局·攒局（最后做）

```
parties
  id BIGINT PK
  user_id UUID FK→users.id       (发起人)
  type VARCHAR(10)               -- group(组局) / purchase(拼单)
  category VARCHAR(20)           -- 自习/电影/聚餐/拼车/拼单/运动/游戏/旅行/其他
  title VARCHAR(200)
  content TEXT
  total INT                      (名额上限)
  joined_count INT DEFAULT 0
  status SMALLINT DEFAULT 1      -- 1招募中 2已满 -1已关闭
  meet_time TIMESTAMPTZ NULL
  location VARCHAR(100) NULL
  created_at TIMESTAMPTZ

party_members
  party_id BIGINT FK→parties.id
  user_id UUID FK→users.id
  joined_at TIMESTAMPTZ DEFAULT now()
  PK(party_id, user_id)
```

- `GET /parties?category=&only_vacant=&cursor=` → 列表（含 joined/total → 进度条）；累计攒局人数 = `count(party_members)`
- `POST /parties`、`GET /parties/{id}`、`POST /parties/{id}/join`、`DELETE /parties/{id}/join`（退出）
- `GET /me/parties`（我加入的局）
- 报名 → joined_count±1，满额自动 status=2，触发通知（模块 C）
- 前端组局页全量接真实 API。

---

## 迁移与测试策略

- 每模块一个 Alembic 迁移（`alembic revision --autogenerate` 后人工核对，加索引/唯一约束）。
- 每个新 service 函数配 pytest（happy + 权限 + 边界，如重复点赞、删他人评论 403、自通知跳过）。
- 计数字段用 `UPDATE ... SET count = count + 1` 而非读改写，避免并发。
- 复用 conftest fixtures；新增 `guest_token` 场景下的 401/403 断言。

## 验收（每模块）

- `cd backend && python -m pytest -v` 全绿（贴输出）
- 关键端点 curl 实测（启动 uvicorn + 真实请求，贴响应）
- 前端对应页从 mock 切真实 API，`npm run type-check` + `build:h5` 绿，人工预览交互生效
