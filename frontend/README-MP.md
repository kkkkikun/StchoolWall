# 微信小程序端 — 构建与开发者工具测试指南

> 小程序正式 AppID 未申请（无资质）期间的兼容性验证方案：本地构建 + 微信开发者工具 + 测试号登录链路。

---

## 1. 前置条件

| 项 | 说明 |
|---|---|
| 微信开发者工具 | Windows 侧安装（无 Linux 版，WSL 用户装到 Windows）：https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html 选 **稳定版 Stable** |
| 后端 | WSL 本地 `:8000` 在跑（Windows 经 WSL2 localhost 转发直接访问 `127.0.0.1:8000`） |
| 登录链路（可选） | 微信**测试号** appid/secret（见 §5） |

## 2. 构建小程序包

```bash
cd frontend
npm run build:mp-weixin
# 产物：frontend/dist/build/mp-weixin/
```

- 当前后端地址取自 `frontend/.env` 的 `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`（连本地 WSL 后端）。
- 连公网服务器测试：`VITE_API_BASE_URL=http://103.36.221.122:8080/api/v1 npm run build:mp-weixin`
- **给别人用的包**必须去掉演示登录：`VITE_DEV_LOGIN= npm run build:mp-weixin`（`.env` 里该值为 true 时，包内会渲染「一键登录（演示学生）」按钮——仅本地 dev 后端可用，生产后端已封该接口）
- CI 管线产物：`ci-artifacts/<时间戳>/mp-weixin/`（服务器跑 CI 后同样可取）

## 3. 导入微信开发者工具

1. **推荐**把 `dist/build/mp-weixin` 整个目录拷到 Windows（如 `D:\schoolwall-mp\`），再「导入项目」选该目录——`\\wsl$\...` 路径直接导入偶发文件监听异常；
2. AppID 选「**测试号**」（或留空后点「使用测试号」）——申请了测试号就填测试号 appid（§5）；
3. 项目设置 → 本地设置 → 勾选「**不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书**」（HTTP + IP 后端必需）。

## 4. 兼容性实测清单

| # | 检查项 | 预期 |
|---|--------|------|
| 1 | 首页信息流渲染 | 卡片/头像/单图铺开/多图 1:1 网格正常 |
| 2 | 游客浏览 | 未登录可看帖/详情/评论列表 |
| 3 | 登录（测试号链路） | 启动即静默登录，「我的」页显示昵称 |
| 4 | 发帖带图 | chooseImage 选图 → 上传 → 帖子显示图片 |
| 5 | 评论 | 发评论正常（灰词提示「审核通过后可见」） |
| 6 | 组局/消息/个人主页 | 页面切换与数据正常 |

## 5. 登录链路（测试号，免费无资质）

1. 访问 https://mp.weixin.qq.com → 「测试号」（或直接 https://mp.weixin.qq.com/wxamp/sandbox?doc=1 ）→ 微信扫码登录；
2. 记下 **appID** 和 **appsecret**；
3. 发给开发者配置到后端：`backend/.env` 的 `WECHAT_APP_ID` / `WECHAT_APP_SECRET` → 重启后端；
4. devtools 项目里 AppID 填**同一个测试号 appid**（两边必须配对，code2session 才能换 openid）；
5. 重新编译 → `App.vue` onLaunch 自动 `uni.login` → 后端 `/auth/login` → 换 JWT → 「我的」页显示昵称即通。

链路已存在于代码（`App.vue #ifdef MP-WEIXIN` → `wxLoginAndStore`），**后端零代码改动，纯配置**。

## 6. 排错

| 症状 | 原因与处理 |
|------|-----------|
| 所有请求「网络请求失败」 | 未勾「不校验合法域名」，或后端没在跑（`curl 127.0.0.1:8000/health`） |
| 登录后仍是游客态 | 后端未配/配错 `WECHAT_APP_ID/SECRET`（未配时静默失败自动降级游客，不报错）——看后端日志 code2session 返回 |
| 图片不显示 | 图片 URL 域名也受 urlCheck 控制（勾选后可加载 http）；或后端 `PUBLIC_BASE_URL` 配置与实际访问不符 |
| 白屏 | devtools Console 看报错；确认导入的是 `dist/build/mp-weixin`（不是 H5 dist） |

## 7. 已知边界（正式上线前必须解决，backlog）

- 正式 AppID + 小程序类目资质（校园社区类需要审核）
- request/uploadFile 合法域名：必须 **HTTPS + 已备案域名**（如 `https://你的域名`），届时 `VITE_API_BASE_URL` 换正式域名，且微信后台「开发管理 → 服务器域名」加白名单
- `flex gap` 在极旧微信内核（iOS<14.5）可能塌陷——真机测试时留意图片网格
