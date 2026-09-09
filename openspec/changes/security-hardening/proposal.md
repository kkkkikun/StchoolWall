# Security Hardening — 全量安全加固

## Why

2026-09-04 三路并行安全审计（认证授权 / 输入与越权 / 信息泄露与配置）发现 **2 Critical + 4 High + 若干 Medium/Low**，其中两个 Critical 在当前 dev 配置下已实际生效：

1. `JWT_SECRET` 使用仓库内公开的占位符（config 默认值 = 当前 .env 实值）→ 任何看过仓库的人可伪造任意用户与管理员 console token
2. `ENVIRONMENT` 默认 `development`（fail-open）→ 生产忘配 .env 时 `/auth/dev-login?as_admin=true` 免密发放完整管理员权限

High：上传接口信任客户端 path（存储型 XSS + 任意覆盖他人头像/横幅）、post.images 触发审核管线 SSRF、CORS `*`+credentials、发帖/评论/举报/上传零限流。Medium 中最关键：**封禁/待审帖可按序号 ID 直读详情并互动，旁路整个审核系统**。

用户已确认（AskUserQuestion 2026-09-04）：全量修复（C+H+M+L 五批）；real_name 自视保留（编辑资料页功能），wechat_id 仅交易类帖型返回；python-jose → pyjwt 随低危批迁移。

## What Changes

- **批1 启动安全闸门**：轮换 JWT_SECRET；生产环境占位密钥 fail-fast；ENVIRONMENT 默认改 production；dev-login 加显式 DEV_LOGIN_ENABLED 双闸；生产关闭 /docs /redoc；全站安全响应头中间件
- **批2 上传收紧**：/upload/direct 弃用客户端 path，改 kind 白名单 + 服务端生成 uuid 路径；_safe_path 改 is_relative_to；流式大小上限
- **批3 访问控制补漏**：封禁/待审帖详情与互动仅 status==1 可见（作者/管理员例外）；post.images 限 /static/ 相对路径（杀死 SSRF）；hot-ranking limit 加界；UUID 路径参数校验
- **批4 限流铺开**：发帖/评论/举报/上传按用户限流；管理台登录加按用户名退避；rate_limit INCR/EXPIRE 原子化
- **批5 低危杂项**：pyjwt 迁移；ILIKE 转义与 q 上限；CSV 公式注入防护；各 body 字段补上限；join_party 行锁防超卖；docker-compose 端口绑定 127.0.0.1；wechat_id 按帖型收敛；MODERATION_FAIL_OPEN 默认改 False

不变项（审计验证为安全）：教务密码内存流转、核心 IDOR 所有权检查、SQL 参数化、admin 全路由 console 门禁、bcrypt 计时防枚举。

## Impact

- 后端：config/main/依赖注入/上传/帖子/互动/限流/导出/若干 schema 与 compose
- 前端：request.ts uploadFile 改传 kind（不传自造 path）
- 兼容性：轮换密钥后所有已发 token 失效（需重新登录）；/upload/direct 参数变化需与前端同步发布
