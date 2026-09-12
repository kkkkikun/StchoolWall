# MP-Weixin Compat — 任务清单

## 批1：代码侧（本地完成）

- [x] T1 静态兼容审计：H5-only API 泄漏（window/document/localStorage/navigator 在 #ifdef H5 之外）、tabBar custom 模式、跨端 API 复查
- [x] T2 `manifest.json` mp-weixin 节点补全（appid 待测试号）
- [x] T3 `npm run build:mp-weixin` 通过 + 产物完整性（app.json、页面齐全）
- [x] T4 发现的兼容问题修复 + 复构建验证
- [x] T5 `frontend/README-MP.md`：devtools 步骤/构建命令/登录验证/排错指引

## 批2：登录链路（用户配合）

- [ ] T6 用户申请微信测试号（mp.weixin.qq.com → 测试号 → appid+secret）
- [ ] T7 后端 `.env` 配 `WECHAT_APP_ID/WECHAT_APP_SECRET` + 重启；本地验证 code2session 可用（devtools 复编译触发 onLaunch）
- [ ] T8 用户 devtools 实测清单：首页渲染/图片显示/游客浏览/登录态发帖带图/评论
