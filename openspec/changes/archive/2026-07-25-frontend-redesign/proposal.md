# Proposal: 前端 UI/UX 大改造（对齐 ref/ 设计稿）

## 为什么做

现有前端 UI/UX 不满意：3-tab、蓝色主题、单卡片列表，信息密度低、缺乏运营位与社区氛围。
`ref/` 提供了 5 个高保真页面设计（首页/组局/发布/消息/我的），红色品牌主题、卡片化、金刚区、信息流、组局拼单等，是更完整的产品形态。

## 做什么

把 `ref/` 的 5 个原生小程序设计稿**翻译为 uni-app (Vue3 + TS)** 实现，作为前端独立预览（mock 数据），让用户先看效果。

- 5 个主 tab 页：首页（信息流+金刚区+热帖）、组局（攒局/拼单列表+进度条）、发布（热搜+版块+正文+媒体+AI 开关）、消息（4 类通知+空态）、我的（红头+统计+菜单）
- 红色品牌主题（`#f73b43`）统一全站
- 自定义 tabBar（SVG 图标，摆脱缺失的 PNG 依赖）
- emoji + 内联 SVG 图标体系（无 40+ PNG 文件）
- 全 mock 静态数据（脱离后端独立预览）
- 保留并红色化二级页：post-detail / verify / admin / my-posts / tags

## 不做什么（Non-goals，本期）

- ❌ 不改后端、数据库（用户明确：前端先看效果，后端后续推进）
- ❌ 不接真实 API（组局/消息/签到/热帖/统计后端尚无；本期全 mock）
- ❌ 不生成 PNG 图标资源（emoji + SVG 占位，生产图标后续单独补）
- ❌ 不实现 AI 协助真实调用、真实签到、真实 IM（仅 UI 与 mock 交互）

## 影响范围

- 前端 only：`frontend/src/` 下 pages / components / utils / static / pages.json / uni.scss / App.vue
- 后端：无改动
- DB：无改动
- 测试：前端无测试体系（SNAPSHOT 已记录），本期以 `npm run type-check` + H5/mp-weixin 编译 + 人工预览为验收

## 回滚方案

- 所有改动在 `frontend/` 内，git 可整体 revert。
- `ref/` 为只读参考，不被改动。
- 旧页面实现保留在 git 历史；新页面覆盖 index/publish/mine，新增 group/message。
- pages.json 改动可还原为 3-tab。
