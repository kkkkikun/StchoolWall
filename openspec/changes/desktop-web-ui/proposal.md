# 电脑端 Web UI（desktop-frontend）

## Why

SchoolWall 目前的用户界面有两个前端：`frontend/` 是 uni-app（微信小程序为主 + H5 预览），
`admin-frontend/` 是运营管理台。两者都不面向「用电脑访问校园墙的学生用户」：

- 小程序/H5 是移动优先布局，在电脑浏览器里要么被压成一条窄栏，要么整体拉伸，信息密度极低；
- 管理台是给运营人员的高密度表格界面，不适合普通同学浏览与发布。

真实场景里，电脑访问是高频入口（宿舍、实验室、图书馆），需要一套**面向电脑浏览器**、
复用同一套后端 API 的独立前端。

## What Changes

- 新增 `desktop-frontend/`：Vue3 + Vite + TypeScript + Element Plus + Pinia + Vue Router + axios，
  与管理台同栈，构建产物以 `/pc/` 为 base，部署在同源 `/pc/` 路径下（不新增容器、不新增域名）。
- 一期覆盖读 + 写主链路：
  - 读：信息流（推荐/最新/热门/精华）、帖子详情、搜索、标签、轮播位、他人主页、消息通知；
  - 写：注册、登录、发帖（含图片上传）、评论、点赞、收藏、关注、修改资料、删除自己的帖子。
- 界面按电脑端重排：顶部导航 + 左侧导航 + 内容区 + 右侧信息栏的三栏布局，
  视觉令牌沿用仓库既有的玫瑰红品牌色，并支持亮/暗双模式。
- 认证沿用后端既有会话体系，**不新增后端接口、不改数据模型、不写迁移**：
  - 访问令牌只放内存，不写 localStorage；
  - HTTPS 页面走 `X-Client-Type: web` 通道，刷新令牌由服务端 HttpOnly cookie 持有；
  - 纯 HTTP 页面里该 cookie 带 `Secure` 会被浏览器丢弃，自动退化为 `X-Client-Type: native`，
    由响应体带回刷新令牌，页面刷新后可恢复会话。上线 HTTPS 后自动切回 web 通道，无需改代码。
- CI 门禁接入：`desktop-frontend` 与另外两个前端同等对待（type-check、node --test、构建、
  `npm audit --audit-level=high`），并纳入 `frontend/scripts/api-contract-check.mjs` 的接口漂移扫描范围。
- 发布制品新增 `web/pc/` 目录，与 `web/h5`、`web/admin` 并列，由部署侧挂到 `/pc/`。

## Impact

- 后端：无改动。不新增接口、不改响应结构、不改数据库结构，因此不需要 Alembic 迁移。
- 前端：新增 `desktop-frontend/` 一个工程；`frontend/scripts/api-contract-check.mjs` 增加一个扫描目录；
  `.github/workflows/ci.yml` 增加桌面端的检查与构建步骤、制品多带一个目录。
- 运维：`deploy/nginx.schoolwall.conf` 需要新增 `location /pc/`（当前部署在手工模式下由
  `dsh-superagent-setup` 的服务器配置脚本维护，与仓库配置同步）。
- 风险：
  - 电脑端与移动端共用同一套 API，接口漂移由契约守卫兜住；
  - 一期没有端到端 UI 走查脚本（浏览器级回归目前只覆盖 H5 与管理台），
    体积预算也尚未覆盖桌面端主 chunk，这两项列入 tasks 待办。
