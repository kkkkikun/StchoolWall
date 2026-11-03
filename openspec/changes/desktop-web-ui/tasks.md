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
- [x] 桌面端主 chunk 体积预算：新增 `desktop-frontend/scripts/bundle-budget-check.py`，
      基线 `desktop-frontend/bundle-baseline.json`（按 2026-11-03 实际产物定：主 chunk 370356 B raw /
      134576 B gzip、全量产物 713864 B raw），接入 CI；负向验证：基线调小 30% 即 exit 1 并指出超出的项
- [x] 浏览器级 UI 回归：新增 `desktop-frontend/scripts/ui-walkthrough.py`（Playwright，
      覆盖信息流、帖子详情、登录、发帖四条关键路径，base 按 `/pc/` 访问），
      配套 `desktop-frontend/scripts/walkthrough_server.py` 与 `desktop-frontend/scripts/desktop_mock_api.py`；
      走查 19 项断言全 PASS、控制台错误 0 条，已接入 CI
- [x] 深色模式与对比度走查：新增 `desktop-frontend/scripts/ui-contrast-audit.py`，
      断言基于 `src/styles/tokens.css` 的令牌（不写死色值），覆盖亮/暗两套配色 × 四条关键路径；
      阻断项 0 条，既有设计差距（品牌色小字、弱化文字、Element Plus 默认占位符色）单列记录不阻断，
      已接入 CI
- [x] 发布路径：`deploy/nginx.schoolwall.conf` 增加 `location /pc/`（alias 指向
      `/opt/schoolwall/current/web/pc/`），并同步到部署侧的服务器配置脚本
- [x] 线上验收（2026-11-02）：主仓合并 cb9511d 后由手工发布上线，revision `cb9511d1cfb7`。
      `/pc/` 首页、SPA 路由回退（`/pc/login`、`/pc/tags`）、静态资源、同源 `/api` 反代、
      登录换令牌全部 200；本地 Chromium 冒烟实测渲染出 3 张信息流卡片、零 console 错误。
      贴士：后端「发帖频率风控」为 10 分钟内最多 3 帖，超限转人工复核；
      staging 演示内容是直接置 `posts.status=1` 通过的。
