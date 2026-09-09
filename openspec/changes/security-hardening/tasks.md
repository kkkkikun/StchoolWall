# Tasks — Security Hardening

> TDD：每批新测试先红后绿，全量 pytest 通过才进下一批。基线 366 passed。

## 批1 启动安全闸门
- [x] tests/test_security_gates.py：validator 三态（占位/短/空 → production 拒；正常通过；dev/test 跳过）+ dev-login 双闸（flag 关 404 / 开+dev 200）
- [x] config.py：ENVIRONMENT 默认 production；DEV_LOGIN_ENABLED=False；MODERATION_FAIL_OPEN=False；validate_security_config()
- [x] main.py：startup 调 validator；生产关 /docs /redoc；安全响应头中间件
- [x] routers/auth.py：dev-login 双条件门禁
- [x] .env 轮换 JWT_SECRET（openssl rand -hex 32）+ DEV_LOGIN_ENABLED=true；重启后 dev-login/boss 重登验证
- [x] 全量 pytest 绿

## 批2 上传收紧
- [x] tests/test_upload_security.py 红：kind 白名单 422 / html 扩展 422 / is_relative_to 逃逸拒 / 正常上传落盘 / 超大小拒
- [x] routers/upload.py：path→kind 白名单 + 服务端 uuid 路径 + 流式大小校验
- [x] utils/storage.py：_safe_path 改 is_relative_to
- [x] frontend/src/utils/request.ts：uploadFile 改传 kind；vue-tsc 0 错
- [x] 修 tests/test_upload.py 调用点；全量 pytest 绿

## 批3 访问控制补漏 + SSRF
- [x] tests/test_access_control.py 红：封禁帖详情 404/作者 admin 200；封禁帖评论点赞 404；images 外链 422；hot-ranking 越界 422；非 UUID 422
- [x] services/post.py：get_post_detail status 门（作者/admin 例外）
- [x] services/interaction.py：_get_post 强制 status==1
- [x] schemas/post.py：images 元素 /static/ 前缀 + 长度校验
- [x] routers/user.py：hot-ranking limit ge/le；interaction/admin UUID 路径 pattern
- [x] 全量 pytest 绿

## 批4 限流铺开
- [x] tests/test_rate_limits_security.py 红：发帖/评论/举报/上传阈值 429；admin 按用户名锁定；键 TTL 断言
- [x] utils/rate_limit.py：SET NX EX 原子化
- [x] routers：posts/interaction/upload 按用户限流；admin_auth 按用户名退避
- [x] 全量 pytest 绿

## 批5 低危杂项 + pyjwt
- [x] pyjwt 迁移（requirements + utils/security.py），全量 token 测试回归
- [x] escape_like + 各 q 参数 max_length=50
- [x] CSV 公式注入前缀；report description/price/tag_ids/password 上限；ZHENGFANG_BASE_URL 空预检
- [x] join_party with_for_update；wechat_id 按交易帖型收敛（测试：非交易帖不返回 contact_wechat）
- [x] docker-compose 端口绑定 127.0.0.1
- [x] rules/spec.md 红线补自视例外说明
- [x] 全量 pytest 绿 + 前端 type-check

## 收尾
- [x] dev 重启 + 手工冒烟（登录/发帖/上传/管理台）
- [ ] SNAPSHOT/tasks/learned 同步；提交（分批、无共同创作者署名、等用户确认）；提交（分批、无共同创作者署名、等用户确认）
