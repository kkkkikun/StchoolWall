# 鄂应墙后端测试指南

## 快速开始

```bash
cd backend
python -m pytest -v              # 运行全部测试
python -m pytest tests/test_auth.py -v   # 只跑认证模块
python -m pytest -k "rate_limit" -v       # 按关键字筛选
```

## 前置条件

1. Docker 容器运行中（PostgreSQL + Redis）
2. 测试数据库 `ey_wall_test` 已创建（首次执行 `docker exec schoolwall-db-1 psql -U eywall -d postgres -c "CREATE DATABASE ey_wall_test"`）
3. 依赖已安装（`pip install -r requirements.txt`）

## 测试架构

### 隔离策略

| 资源 | 策略 | 说明 |
|------|------|------|
| PostgreSQL | 独立测试库 `ey_wall_test` | 不污染开发数据 |
| 数据库连接 | NullPool 引擎 | 每个 SQL 操作用完即释放，避免 asyncpg 跨事件循环冲突 |
| Redis | 每测试新建客户端 | 注入到业务模块，测试结束自动 flushdb |
| 表数据 | 每测试前 TRUNCATE | conftest `autouse` fixture 自动清理 |

### conftest.py 核心 Fixtures

| Fixture | 类型 | 作用 |
|---------|------|------|
| `setup_database` | session 级, autouse | 建表一次，session 结束时删表 |
| `_clean_before_test` | function 级, autouse | 每测试前清空所有表 + Redis |
| `client` | function 级 | httpx AsyncClient，自动注入测试 DB |
| `guest_user` | function 级 | 创建一个未认证的游客用户 |
| `student_user` | function 级 | 创建一个已认证的学生用户 |
| `admin_user` | function 级 | 创建一个管理员用户 |
| `test_redis` | function 级 | 当前事件循环的独立 Redis 客户端 |
| `guest_token` / `student_token` / `admin_token` | function 级 | 对应用户的 JWT |

### 在新测试中使用

```python
@pytest.mark.asyncio
async def test_something(client, student_user, test_redis):
    token = create_access_token({"sub": str(student_user.id), "role": "student"})
    r = await client.get("/api/v1/xxx", headers=auth_header(token))
    assert r.status_code == 200
```

## 测试文件索引

### test_security.py — JWT 工具单测

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_create_and_decode` | 签发 Token 后能正确解析出 sub、role、exp | JWT 签发/验签链路正常 |
| `test_decode_invalid_token` | 乱码字符串返回 None | 非法 Token 不会被误解析 |
| `test_decode_empty_string` | 空字符串返回 None | 边界情况不崩溃 |
| `test_decode_tampered_token` | 篡改后返回 None | Token 防篡改机制有效 |
| `test_payload_preserves_all_fields` | 自定义字段完整保留 | 可在 Token 中携带任意声明 |
| `test_custom_expiry` | 自定义过期时间生效 | 短期 Token 机制可用 |

### test_rate_limit.py — Redis 限流器单测

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_allows_within_limit` | 5 次请求全部通过 | 限流器不误拦正常请求 |
| `test_blocks_over_limit` | 第 4 次请求（上限 3）触发 HTTPException 429 | 超限拦截机制有效 |
| `test_different_keys_independent` | key1 达上限不影响 key2 | IP 限流和 OpenID 限流互不干扰 |
| `test_counter_increments` | INCR 计数器正确递增 | Redis 计数逻辑可靠 |

### test_auth.py — 认证接口集成测试

#### 微信静默登录 POST /api/v1/auth/login

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_new_user_creates_guest` | 新 openid 自动创建用户，返回 guest 角色 JWT | 首次打开小程序的完整链路 |
| `test_returning_user_gets_existing_role` | 已有 student 用户登录返回 student 角色 | 老用户登录状态不丢失 |
| `test_invalid_code_returns_error` | 微信返回 errcode 时返回 400 | 无效 code 不会导致崩溃 |
| `test_missing_code_field` | 缺少 code 字段返回 422 | Pydantic 参数校验生效 |
| `test_empty_code_field` | 空字符串 code 返回 422 | 空值不被放行 |

#### 学籍认证绑定 POST /api/v1/auth/verify

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_verify_success` | 爬虫返回成功后 real_name 落库，角色升级为 student | **核心链路**：认证→抓取姓名→写库→升级 |
| `test_verify_wrong_password` | 教务系统密码错误返回 code=400 | 不会因为密码错误而崩溃 |
| `test_verify_student_id_already_bound` | 学号被他人绑定返回 409 | 一人一号的强绑定逻辑有效 |
| `test_verify_already_verified` | 已认证用户再次认证被拒绝 | 防重复绑定 |
| `test_verify_requires_token` | 无 Token 返回 403 | 接口受鉴权保护 |
| `test_verify_missing_fields` | 缺少 password 字段返回 422 | 参数校验完整 |
| `test_verify_rate_limit_by_ip` | 11 次请求后返回 429 | IP 限流防护生效 |

### test_posts.py — 帖子模块集成测试

#### 发帖 POST /api/v1/posts

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_student_create_post` | student 发帖成功，初始状态 0（待审核） | 学生发帖基础链路 |
| `test_admin_create_post_auto_approved` | admin 发帖状态直接为 1 | 管理员免审核机制 |
| `test_admin_create_advertisement` | admin 可发 advertisement 类型 | 广告发布权限正确 |
| `test_student_cannot_create_advertisement` | student 发广告返回 403 | 广告权限隔离有效 |
| `test_create_post_with_all_fields` | 带 images、price 的帖子正常创建 | 扩展字段写入正常 |
| `test_guest_cannot_create_post` | guest 发帖返回 403 | 未认证用户无法发帖 |
| `test_no_token_cannot_create` | 无 Token 发帖返回 403 | 接口受鉴权保护 |

#### 帖子列表 GET /api/v1/posts

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_empty_list` | 无帖子时返回空列表和 has_more=false | 空状态不报错 |
| `test_list_returns_visible_posts` | 只返回 status=1 的非广告帖 | 可见性过滤正确 |
| `test_advertisements_pinned` | 广告帖排在普通帖前面 | 置顶逻辑有效 |
| `test_list_public_no_token` | 无 Token 可访问列表 | 公开接口无需登录 |
| `test_list_does_not_expose_real_name` | 列表中不暴露 real_name | 隐私保护生效 |

#### 帖子详情 GET /api/v1/posts/{post_id}（隐私隔离）

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_admin_sees_everything` | admin 可看 real_name、student_id、contact_wechat | 管理员全量权限 |
| `test_author_sees_own_real_name` | 作者看自己的帖子能看到 real_name | 自有内容权限正确 |
| `test_student_sees_wechat_but_not_real_name` | 其他 student 能看 wechat_id，看不到 real_name | C2C 联系方式暴露合理 |
| `test_guest_sees_nothing_sensitive` | guest 无 contact_wechat、无 real_name | 游客隐私隔离 |
| `test_nonexistent_post` | 不存在的帖子返回 404 | 资源不存在处理正确 |

#### 状态变更 PUT /api/v1/posts/{post_id}/status

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_author_archive_post` | 作者标记已解决 → status=2 | 状态流转 1→2 正常 |
| `test_author_soft_delete` | 作者软删除 → status=-2 | 状态流转 1→-2 正常 |
| `test_admin_block_post` | admin 封禁帖子 → status=-1 | 管理员封禁权限 |
| `test_cannot_archive_others_post` | 不能归档别人的帖子 → 400 | 权限隔离 |
| `test_invalid_transition` | 从 0 直接到 2 被拒绝 → 400 | 状态机校验有效 |

#### 举报 POST /api/v1/posts/{post_id}/report

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_report_success` | 举报成功且帖子状态不变 | 举报不影响帖子可见性 |
| `test_report_nonexistent_post` | 举报不存在的帖子 → 404 | 资源不存在处理正确 |
| `test_guest_cannot_report` | guest 举报返回 403 | 未认证用户无法举报 |

### test_upload.py — 文件上传模块集成测试

#### 获取上传配置 GET /api/v1/upload/config

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_local_config` | local 模式返回 POST 策略和 direct 接口地址 | 本地存储配置下发正确 |
| `test_r2_config` | R2 模式返回 PUT 策略和预签名 URL（mock boto3） | Cloudflare R2 集成链路正确 |
| `test_admin_can_get_config` | admin 能获取上传配置 | 管理员权限正确 |
| `test_guest_cannot_get_config` | guest 返回 403 | 未认证用户无法获取配置 |
| `test_no_token_rejected` | 无 Token 返回 403 | 接口受鉴权保护 |
| `test_invalid_file_type_rejected` | .exe 文件被拒绝 → 400 | 文件类型白名单生效 |
| `test_invalid_content_type_rejected` | video/mp4 被拒绝 → 400 | content_type 校验生效 |
| `test_missing_filename_rejected` | 缺少 filename 返回 422 | 参数校验生效 |

#### 本地直接上传 POST /api/v1/upload/direct

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_upload_success` | 上传图片成功，返回 public_url | 本地存储写入正常 |
| `test_upload_png` | PNG 格式上传成功 | 多图片格式支持 |
| `test_upload_rejects_non_image` | PDF 上传被拒绝 → 400 | 非图片拦截 |
| `test_upload_guest_forbidden` | guest 返回 403 | 未认证用户无法上传 |
| `test_upload_no_token_rejected` | 无 Token 返回 403 | 接口受鉴权保护 |
| `test_upload_missing_path_rejected` | 缺少 path 参数返回 422 | 参数校验生效 |

### test_tags.py — 标签管理集成测试

#### 标签列表 GET /api/v1/tags

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_empty_list` | 无标签时返回空列表 | 空状态不报错 |
| `test_list_returns_all_tags` | 返回所有已创建标签 | 列表查询正确 |
| `test_list_public_no_token` | 无 Token 可访问 | 公开接口无需登录 |

#### 创建标签 POST /api/v1/tags

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_admin_create_tag` | admin 创建标签成功 | 标签创建链路正常 |
| `test_duplicate_name_rejected` | 重复标签名返回 409 | 唯一性约束生效 |
| `test_student_cannot_create` | student 返回 403 | 权限隔离正确 |
| `test_no_token_cannot_create` | 无 Token 返回 403 | 接口受鉴权保护 |
| `test_empty_name_rejected` | 空标签名返回 422 | 参数校验生效 |

#### 删除标签 DELETE /api/v1/tags/{tag_id}

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_admin_delete_tag` | admin 删除成功，列表确认已删除 | 级联删除正常 |
| `test_delete_nonexistent_tag` | 不存在的标签返回 404 | 资源不存在处理正确 |
| `test_student_cannot_delete` | student 返回 403 | 权限隔离正确 |

### test_admin.py — Admin 管理后台集成测试

#### 举报列表 GET /api/v1/admin/reports

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_admin_list_reports` | admin 查看举报列表含帖子信息 | 举报列表查询正确 |
| `test_filter_by_status` | 按状态过滤举报 | 状态过滤生效 |
| `test_student_cannot_list_reports` | student 返回 403 | Admin 接口权限隔离 |
| `test_no_token_rejected` | 无 Token 返回 403 | 接口受鉴权保护 |

#### 处理举报 PUT /api/v1/admin/reports/{id}

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_dismiss_report` | 驳回举报，状态变为 dismissed | 举报驳回链路正常 |
| `test_ban_post` | 封禁帖子，post.status=-1 | 封禁帖子链路正常 |
| `test_ban_user` | 封禁用户，帖子-1 + 用户冻结 | 最重处罚完整链路 |
| `test_handle_nonexistent_report` | 不存在的举报返回 404 | 资源不存在处理正确 |
| `test_cannot_handle_twice` | 已处理的举报不能重复操作 | 幂等性保护 |

#### 用户列表 GET /api/v1/admin/users

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_admin_list_users` | admin 查看用户列表 | 用户列表查询正确 |
| `test_student_cannot_list_users` | student 返回 403 | Admin 接口权限隔离 |

#### 冻结/解冻用户 PUT /api/v1/admin/users/{id}/status

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_freeze_user` | 冻结用户 status=0 | 用户冻结链路正常 |
| `test_unfreeze_user` | 解冻用户 status=1 | 用户解冻链路正常 |
| `test_nonexistent_user` | 不存在的用户返回 404 | 资源不存在处理正确 |
| `test_student_cannot_freeze` | student 返回 403 | Admin 接口权限隔离 |

### test_moderation.py — 异步审核任务测试

#### 后台审核任务

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_student_post_triggers_moderation` | student 发帖触发后台任务，status 0→1 | BackgroundTasks 调用正确，状态流转正常 |
| `test_post_without_images_passes_directly` | 无图片帖子直接通过 | 空 images 跳过审核 |
| `test_admin_post_skips_moderation` | admin 发帖不触发后台任务（已 status=1） | Admin 免审核机制生效 |
| `test_moderation_failure_blocks_post` | Mock 审核失败，status 0→-1 | 违规内容封禁链路正常 |
| `test_text_moderation` | Mock 文本审核失败，status 0→-1 | 文本审核（可选）机制可用 |

### test_user.py — 用户资料接口集成测试

#### 获取资料 GET /api/v1/user/profile

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_student_can_see_own_profile` | student 可查看自己的 nickname、real_name、student_id、wechat_id | 个人资料完整返回 |
| `test_admin_can_see_own_profile` | admin 同样可查看完整资料 | admin 权限正确 |
| `test_guest_forbidden` | guest 角色返回 403 | 未认证用户无法查看资料 |
| `test_no_token_forbidden` | 无 Token 返回 403 | 接口受鉴权保护 |
| `test_invalid_token_unauthorized` | 伪造 Token 返回 401 | Token 验证机制有效 |
| `test_user_not_in_db_unauthorized` | Token 中用户不存在返回 401 | 防止幽灵 Token |
| `test_frozen_user_forbidden` | status=0 用户返回 403 | 被冻结账号无法使用 |

#### 更新资料 PUT /api/v1/user/profile

| 测试 | 验证内容 | 通过意味着 |
|------|----------|------------|
| `test_update_nickname` | 只改昵称，GET 验证已更新 | 部分更新生效 |
| `test_update_wechat_id` | 只改微信号，GET 验证已更新 | C2C 联系方式可修改 |
| `test_update_both_fields` | 同时改两个字段都生效 | 批量更新正常 |
| `test_update_nothing` | 空请求不报错 | 幂等性安全 |
| `test_guest_forbidden` | guest 返回 403 | 未认证用户无法修改 |
| `test_no_token_forbidden` | 无 Token 返回 403 | 接口受鉴权保护 |
| `test_real_name_not_changeable` | 更新后 real_name 不变 | 真实姓名锁定不可改 |
| `test_nickname_too_long` | 51 字符昵称返回 422 | 字段长度校验生效 |
| `test_empty_nickname_rejected` | 空昵称返回 422 | 空值不被放行 |

## Mock 策略

| 外部依赖 | Mock 方式 | 原因 |
|----------|-----------|------|
| 微信 API（jscode2session） | `patch("app.services.auth.httpx.AsyncClient")` | 避免真实请求微信服务器 |
| 正方教务系统 | `patch("app.services.auth.verify_student")` | 避免真实请求教务系统，保护校园网 IP |
| 微信内容审核 | 后续补充 | 避免消耗审核配额 |

Mock 示例参考 `test_auth.py` 中的 `_mock_wx_response` 和 `_mock_async_client` 工具函数。

## 新增测试的检查清单

实现新接口时，确保覆盖以下场景：

- [ ] 正常流程（happy path）
- [ ] 无 Token 访问 → 403
- [ ] 无效/伪造 Token → 401
- [ ] 权限不足的角色 → 403
- [ ] 参数缺失 → 422
- [ ] 参数越界（超长、空值、非法值）→ 422
- [ ] 业务冲突（如重复绑定）→ 409
- [ ] 外部依赖通过 Mock 隔离
