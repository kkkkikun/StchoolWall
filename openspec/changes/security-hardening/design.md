# Design — Security Hardening

## 批1 启动安全闸门

**config.py**
- `ENVIRONMENT: str = "production"`（fail-secure；dev 靠 .env 显式声明）
- `JWT_SECRET` 保留字段但加启动校验：新增 `validate_security_config()`——`ENVIRONMENT == "production"` 时，密钥为空、等于占位符 `your_super_secret_key_change_me`、或长度 < 32 → `RuntimeError` 拒绝启动。test/development 不强制
- 新增 `DEV_LOGIN_ENABLED: bool = False`；dev-login 门禁改为 `ENVIRONMENT == "development" and DEV_LOGIN_ENABLED` 双条件（`.env` 写 `DEV_LOGIN_ENABLED=true`）
- `MODERATION_FAIL_OPEN: bool = False`（合规优先；未配置微信层时不受影响——未配置直接 pass 不走 error 分支）

**main.py**
- lifespan/startup 调 `validate_security_config()`
- `docs_url=redoc_url=None`（仅 production；用 `settings.ENVIRONMENT != "production"` 表达式）
- 安全响应头中间件（纯 ASGMiddleware 或 @app.middleware）：`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`。CSP 对 JSON API 收益低，不加（静态由 StaticFiles 服务，历史文件已限图片扩展名）

**.env（本地 dev，不入库）**：`JWT_SECRET` 轮换为 `openssl rand -hex 32`；加 `DEV_LOGIN_ENABLED=true`。轮换后所有已发 token 失效——dev 需重新 dev-login、boss 重新登录（密码 Admin@2026）。

**测试** `tests/test_security_gates.py`：validator 占位符/短密钥/空密钥在 production 抛 RuntimeError；正常密钥通过；dev/test 环境跳过；dev-login：flag 关 → 404（即使 ENVIRONMENT=development），flag 开+development → 200。

## 批2 上传收紧

**routers/upload.py `/upload/direct`**
- 参数 `path: str` → `kind: str = Query(..., pattern="^(avatars|banners|posts|parties)$")`
- 服务端生成落盘路径：`f"{kind}/{datetime.now().year}/{uuid4().hex}{ext}"`，`ext` 取自 `validate_file` 校验过的 multipart 文件名——扩展名校验对象与落盘对象从此是同一个
- 大小校验改流式：分块读累计，超 `MAX_FILE_SIZE` 即拒（不再整读内存后判断）

**utils/storage.py**
- `_safe_path`：`str(full).startswith(str(base))` → `full.is_relative_to(base)`（杀 `../static-evil` 兄弟目录逃逸）
- 保留 `save_upload(file, path)` 签名（路径由路由层生成，不再来自客户端）

**frontend/src/utils/request.ts**：`uploadFile(filePath, kind)` 直接传 kind（去掉 `Date.now().jpg` 自造路径）。`/admin/upload/image` 已是服务端生成，不动。

**测试** `tests/test_upload_security.py`：kind 白名单外 422；`.html/.svg` 扩展名 422；`is_relative_to` 逃逸用例单元级；正常上传返回 `/static/{kind}/...` 路径且文件存在；超大小拒。改 `tests/test_upload.py` 调用点（path→kind）。

## 批3 访问控制补漏 + SSRF

**services/post.py `get_post_detail`**
- 陌生人视角仅 `status == 1` 可见；作者本人与 admin 可见自己的 0/-1/-2（我的帖子页点进待审帖要能看）
- 未通过 → 404（不区分"不存在/不可见"，避免存在性探测）

**services/interaction.py `_get_post`**（like/comment/favorite 共用）
- 强制 `post.status == 1`，否则 404——封禁帖不能再被点赞评论（作者对自己待审帖 likewise 拒绝，行为一致）

**schemas/post.py `PostCreate.images`**
- 元素校验：必须以 `/static/` 开头且 ≤ 200 字符（pydantic validator）。前端本就只传自家上传返回的相对路径；外部图床 URL 从此 422
- **SSRF 根因消除**：`wechat_client.load_image_bytes` 的 http 分支对 post.images 成为死代码，保留但不再可达；不改其逻辑（banner 等管理端外部 URL 不经过它）

**routers/user.py hot-ranking**：`limit: int = Query(5, ge=1, le=50)`

**UUID 路径校验**：interaction.py 的 `{user_id}` 路由与 admin 用户路由加 `Path(..., pattern=uuid4 格式)`，非 UUID → 422（消除 500 噪音）

**测试** `tests/test_access_control.py`：封禁帖详情 404（陌生人）/200（作者、admin）；对封禁帖评论/点赞 404；images 外链 422；hot-ranking limit=99999 → 422；非 UUID user 路由 422。

## 批4 限流铺开

**utils/rate_limit.py**
- 原子化：`SET key 0 EX window NX` → `INCR`（首建即带 TTL，消灭无 TTL 永久限流键）
- 复用 `check_rate_limit`（抛 429），限流值集中为命名常量

**按用户限流**（key `rl:u:{user_id}:{action}`，叠加在现有 IP 层之外）：
| 动作 | 阈值 |
|---|---|
| 发帖 | 10 次/小时 +（已有频率风控转人工兜底） |
| 评论 | 30 次/10 分钟 |
| 举报 | 10 次/10 分钟 |
| 上传 | 30 次/小时 |

**管理台登录**：加按用户名计数 `rl:admin_user:{username}` 连续失败 5 次/10 分钟 → 429（ bcrypt 之外的第二道闸；不做永久锁定防 DoS 管理员）

**测试** `tests/test_rate_limits_security.py`：连发帖子第 11 次 429；评论/举报/上传各自阈值；admin 登录错 5 次后正确密码也 429（窗口内）；INCR 键带 TTL（redis ttl > 0 断言）。

## 批5 低危杂项 + pyjwt

- **pyjwt**：requirements `python-jose[cryptography]==3.3.0` → `pyjwt==2.10.*`（npmmirror 对应 pip 源装）；`utils/security.py` 改 `import jwt`（HS256、同 claims、`options={"verify_exp": ...}` 保持现状语义）。现有 token 测试即迁移回归
- **ILIKE 转义**：`utils/query.py` 新增 `escape_like(q)`（转义 `\ % _`），应用于公开搜索 + 各 admin q 筛选；所有 `q` 参数加 `max_length=50`
- **CSV 公式注入**：`admin_export.py` 单元格以 `= + - @` 开头时前缀 `'`
- **body 上限补齐**：`ReportRequest.description max_length=1000`；`PostCreate.price le=10_000_000`；`tag_ids` 列表 ≤ 10；verify `password max_length=100` + `ZHENGFANG_BASE_URL` 为空时返回明确 400 而非 500
- **join_party**：`select(Party).with_for_update()` 消除超卖竞态
- **wechat_id 收敛**：`services/post.py` contact_wechat 仅 `post_type in TRADE_POST_TYPES = {"secondhand", "jobs"}` 返回（按用户决策；其他帖型不泄露）
- **docker-compose**：`5432/6379` 端口绑定 `127.0.0.1:`，注释提示生产加 requirepass 与强密码
- **spec 修订**：rules/spec.md 红线补一句"real_name/student_id 自视（本人 token）允许，公开响应禁止"

**测试**：pyjwt 迁移跑全量 token 相关；escape_like 单元；CSV 前缀断言；price 越界 422；wechat_id 非交易帖型不返回；join_party 并发（顺序双请求模拟 check-then-act 已无法复现竞态，断言 with_for_update 生效路径 + 超员拒加）。

## 验证方式

每批 TDD：新测试红 → 实现 → 绿 → 全量 pytest（366+ 基线）。批2 需同步 `vue-tsc`。收尾：dev 重启（新密钥）→ dev-login/boss 重登 → 发帖/上传/管理台抽查回归；`alembic` 无涉（本变更无 DB 结构变化）。
