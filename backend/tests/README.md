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
