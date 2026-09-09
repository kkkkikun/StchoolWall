# Security Spec Delta

## ADDED Requirements

### Requirement: 启动安全闸门

服务在任何非 development/test 环境下 MUST 拒绝使用占位/过短的 JWT 密钥启动；dev-login 路由 MUST 同时满足 ENVIRONMENT=development 与 DEV_LOGIN_ENABLED=true 才可用。

#### Scenario: 生产环境占位密钥拒绝启动
- **WHEN** ENVIRONMENT=production 且 JWT_SECRET 为空/占位符/长度<32
- **THEN** 启动时抛 RuntimeError，进程退出

#### Scenario: dev-login 双闸
- **WHEN** DEV_LOGIN_ENABLED 未显式开启（默认 False）
- **THEN** POST /auth/dev-login 返回 404，即使 ENVIRONMENT=development

#### Scenario: 生产关闭交互式文档
- **WHEN** ENVIRONMENT=production
- **THEN** /docs 与 /redoc 返回 404

#### Scenario: 安全响应头
- **WHEN** 任意 API 响应
- **THEN** 携带 X-Content-Type-Options: nosniff 与 X-Frame-Options: DENY

### Requirement: 安全上传

上传接口 MUST NOT 信任客户端提供的落盘路径；落盘路径 MUST 由服务端从白名单目录前缀 + 随机文件名生成；路径 containment 检查 MUST 使用路径包含语义而非字符串前缀。

#### Scenario: 扩展名校验作用于落盘文件
- **WHEN** 客户端以合法 multipart 文件名（x.jpg）请求写入任意扩展（kind 白名单外或扩展不允许）
- **THEN** 请求被拒（422），无文件落盘

#### Scenario: 不可覆盖既有文件
- **WHEN** 同一用户重复上传
- **THEN** 每次落盘路径均不同（uuid），既有公共资源不可被覆盖

### Requirement: 内容可见性与互动门禁

非 status==1 的帖子（待审/封禁/删除）MUST NOT 对非作者非管理员展示详情，MUST NOT 接受点赞/评论/收藏。

#### Scenario: 封禁帖对陌生人不可见
- **WHEN** 普通用户请求封禁帖详情
- **THEN** 404

#### Scenario: 作者可自查
- **WHEN** 作者请求自己待审/封禁帖详情
- **THEN** 200 正常返回

#### Scenario: 封禁帖不可互动
- **WHEN** 任何用户对封禁帖点赞/评论/收藏
- **THEN** 404

### Requirement: 图片输入域限制

帖子 images 元素 MUST 为 /static/ 开头的相对路径（长度 ≤200），禁止任意外部 URL 进入服务端取回链路（SSRF 根因消除）。

#### Scenario: 外链图片拒绝
- **WHEN** PostCreate.images 含 http(s):// 或其他非 /static/ 前缀元素
- **THEN** 422

### Requirement: 写操作限流

发帖/评论/举报/上传 MUST 具备按用户维度的频率上限（Redis 计数）；管理台登录 MUST 具备按用户名的失败退避；限流键 MUST 自建即带 TTL。

#### Scenario: 超频发帖
- **WHEN** 同一用户 1 小时内发帖超过阈值
- **THEN** 429

#### Scenario: 管理台用户名退避
- **WHEN** 同一用户名 10 分钟内登录失败超过 5 次
- **THEN** 该用户名后续尝试（含正确密码）429

### Requirement: 敏感字段最小暴露

wechat_id（contact_wechat）MUST 仅在交易类帖型（secondhand/jobs）返回；real_name/student_id 仅允许本人自视与管理员范围（既有红线 + 自视例外成文）。

#### Scenario: 非交易帖不泄露微信号
- **WHEN** 认证学生查看 general 帖详情
- **THEN** 响应不含 contact_wechat

### Requirement: 输入卫生

搜索词 MUST 转义 ILIKE 通配符并限长；CSV 导出单元格 MUST 防公式注入；各 body 字段 MUST 有显式上限（举报描述/价格/tag 数/密码长度）。

#### Scenario: CSV 公式注入防护
- **WHEN** 帖子内容以 = + - @ 开头
- **THEN** 导出单元格加 ' 前缀
