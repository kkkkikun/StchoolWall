# Tasks — 电脑端 Web UI（desktop-frontend）

## 批1：工程骨架与契约接入

- [x] 新增 `desktop-frontend/` 工程（Vue3 + Vite + TS + Element Plus + Pinia + Router + axios），
      `package.json` 脚本对齐管理台：`dev` / `build` / `build:desktop`（`--base=/pc/`）/ `type-check` / `test`
- [x] 设计令牌集中在 `src/styles/tokens.css`：品牌色沿用玫瑰红 `#c2455c`，亮/暗双模式只覆写令牌
- [x] API 层集中在 `src/api/*.ts`（顶层 .ts），HTTP 封装放 `src/utils/http.ts`，
      避免把 `/api/v1` 这类非接口字面量带进契约扫描目录
- [x] `frontend/scripts/api-contract-check.mjs` 增加 `desktop-frontend/src/api` 扫描目录，
      本地执行 `node frontend/scripts/api-contract-check.mjs` 退出码 0
- [x] `.github/workflows/ci.yml` 增加桌面端 `npm ci` / `type-check` / `test` / `build:desktop` /
      `npm audit --audit-level=high`，发布制品新增 `web/pc/` 目录

## 批2：读链路

- [x] 信息流页：推荐 / 最新 / 热门 / 精华四个视角，游标翻页，轮播位，空态与加载态
- [x] 帖子详情页：正文、图片、互动计数、点赞、收藏、删除自己的帖子
- [x] 评论列表与评论输入，删除自己的评论
- [x] 搜索页与标签总览页、按标签浏览
- [x] 他人主页：资料、帖子列表、关注
- [x] 消息通知页：分类筛选、标记已读、全部已读

## 批3：写链路

- [x] 注册（登录名 2–20 位、密码 ≥10 位）、登录、退出登录
- [x] 发帖：版块、正文、价格、标签、图片上传（走 `media_ids`，生产环境禁止直传 `images`）
- [x] 修改资料（昵称、简介、微信号）、查看与下线登录设备
- [x] 会话恢复：刷新页面后用刷新通道接回会话；访问令牌只放内存

## 批4：验证与规范

- [x] `npm run type-check` 无报错
- [x] `npm test`（node --test）覆盖映射层与 HTTP 封装：17 项全绿
- [x] `npx @fission-ai/openspec@1.4.1 validate --specs` 通过
- [ ] 桌面端主 chunk 体积预算：新建 `desktop-frontend/bundle-baseline.json`，
      并扩展 `frontend/scripts/perf-budget-check.py` 或新增独立预算脚本，接入 CI
- [ ] 浏览器级 UI 回归：补 `desktop-frontend/scripts/*-walkthrough.py`（Playwright），
      覆盖信息流、详情、登录、发帖四类关键路径
- [ ] 深色模式与对比度走查：走查断言基于令牌而非色值，正文对比度 ≥4.5:1
- [ ] 发布路径：`deploy/nginx.schoolwall.conf` 增加 `location /pc/`（alias 指向
      `/opt/schoolwall/current/web/pc/`），并同步到部署侧的服务器配置脚本
- [ ] 线上验收：`/pc/` 可访问，接口走同源 `/api`，登录后能发帖与评论
