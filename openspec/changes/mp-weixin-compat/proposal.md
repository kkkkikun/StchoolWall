# MP-Weixin Compat — 小程序构建 + devtools 兼容验证 + 登录链路

## Why

小程序正式 AppID 暂时申请不下来（无资质），但用户要**尽早验证 uni-app 代码在微信小程序端的兼容性**，并跑通登录链路。用户已确认（2026-09-11 AskUserQuestion）：做「加登录链路」深度——申请微信**测试号**（免费、无资质要求）拿 appid/secret 配到后端，跑通 `wx.login` 静默登录全链路。

现状（已核实）：
- `build:mp-weixin` 脚本在；`manifest.json` mp-weixin `appid` 为空、`urlCheck: false`
- 非 H5 平台 `DEFAULT_BASE = http://127.0.0.1:8000/api/v1`（`VITE_API_BASE_URL` 可覆盖）——连本地 WSL 后端即用
- `App.vue` onLaunch 已有 `#ifdef MP-WEIXIN` 静默登录（`uni.login` → `/auth/login` → 后端 code2session）；后端未配 `WECHAT_APP_ID/SECRET` 时登录失败自动降级游客态，不阻塞
- 微信开发者工具无 Linux 版 → 用户在 Windows 侧安装，导入 `dist/build/mp-weixin`（WSL 路径或拷贝）

## What Changes

- `manifest.json`：mp-weixin 节点补全（appid 留空待测试号，最小配置）
- 静态兼容审计：grep H5-only API（`window.`/`document.`/`localStorage`）在 `#ifdef H5` 之外的泄漏；pages.json tabBar custom 模式在 MP 的支持
- `npm run build:mp-weixin` 构建通过 + 产物完整性检查（app.json/页面文件齐全）
- 发现的兼容问题修复（以实际构建/审计结果为准，Surgical）
- 后端零代码改动：登录链路只配 `WECHAT_APP_ID/WECHAT_APP_SECRET` env（测试号凭证）+ 重启
- `frontend/README-MP.md`：devtools 导入步骤、「不校验合法域名」勾选、连本地 vs 连公网后端的构建命令、登录链路验证步骤、测试号申请指引

## Impact

- `frontend/src/manifest.json`（配置补全）
- 可能的少量前端兼容修复（以审计/构建发现为准）
- 新增 `frontend/README-MP.md`
- devtools 实测与登录链路验证由用户在 Windows 侧执行（我给清单与排错指引）
- 正式上线小程序仍需：正式 AppID + HTTPS 已备案域名（`request` 合法域名）——记 backlog，不在本次范围
