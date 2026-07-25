# Design: 前端 UI/UX 大改造

> 版本：1.0 ｜ 2026-07-06

## 1. 设计稿翻译策略（wxml/wxss/js → uni-app Vue3）

ref/ 是原生微信小程序（`.wxml`/`.wxss`/`.js`），本项目是 uni-app (Vue3 + TS)。翻译映射：

| 原生小程序 | uni-app Vue3 |
|------------|--------------|
| `.wxml` `<view>` | `<template>` 内 `<view>`（uni-app 原生支持 view） |
| `bindtap` | `@tap` / `@click` |
| `wx:for` / `wx:key` | `v-for` / `:key` |
| `wx:if` | `v-if` |
| `rpx` 单位 | `rpx`（uni-app H5/mp 均支持） |
| `Page({ data, setData })` | `<script setup>` + `ref`/`reactive`，直接赋值 |
| `wx.*` | `uni.*` |
| `wx.navigateTo/switchTab` | `uni.navigateTo` / `uni.switchTab` |
| `<icon type="search">` / `<image src=*.png>` | `<UiIcon name="search"/>` 自研 SVG 组件 / emoji |

## 2. 主题与设计 Token

在 `uni.scss` 与 `App.vue` 全局样式定义 CSS 变量（设计 token），全站复用：

```
--brand-red: #f73b43        主品牌红（头部/按钮/tab 高亮）
--brand-red-dark: #ff3b30   强调红（角标/热标）
--bg-page: #f7f8fa          页面灰底
--bg-group: #fff9f5         组局页暖米底
--radius-card: 24rpx        卡片圆角（对应 ref var(--radius-main)）
--radius-btn: 44rpx         胶囊按钮圆角
```

替换旧蓝色 `$uni-color-primary: #007aff` → 红色系。

## 3. 图标体系（emoji + 内联 SVG）

- **分类/运营图标**（金刚区 10 项、组局 10 类、消息 4 类、菜单项）：用 emoji（ref 组局页本就用 emoji）。
- **操作图标**（搜索/分享/收藏/赞/评论/箭头/加号/定位/图层/对勾/返回等 ~15 个）：自研 `components/ui-icon.vue`，name prop 切换内联 SVG path，currentColor 继承。
- **头像/图片**：用彩色 emoji 或 CSS 渐变圆占位（避免外链图片）。
- 不生成任何 PNG。

## 4. 自定义 TabBar

- `pages.json` 注册 5 个 tab 页，`tabBar.custom = true`。
- 自研 `components/tab-bar.vue`：固定底部，5 项（首页/组局/发布/消息/我的），SVG 图标 + 文字，当前页高亮红色。
- 切换用 `uni.switchTab({ url })`。
- 每个 tab 页在 onShow 调 `uni.hideTabBar()`（双保险）并渲染 `<TabBar :current="n"/>`。
- 平台：H5 + mp-weixin 行为一致。

## 5. Mock 数据层

新建 `utils/mock.ts`，集中所有 ref/ 样例数据：
- hotPosts、menuItems（金刚区）、tabs（首页分类）、feeds（信息流）
- partyCategories、partyList（组局）
- messageCategories、dynamicMessages（消息，默认空触发"暂无消息"）
- userInfo、userStats、menuGroup1/2（我的）
- hotTags（发布热搜）

类型放 `types/mock.ts`，与现有 `types/api.ts` 分离（mock 不污染真实 API 契约）。

## 6. 文件清单

**新增：**
- `frontend/src/components/ui-icon.vue`（SVG 图标）
- `frontend/src/components/tab-bar.vue`（自定义底栏）
- `frontend/src/components/feed-card.vue`（首页信息流卡片）
- `frontend/src/utils/mock.ts`（mock 数据）
- `frontend/src/types/mock.ts`（mock 类型）
- `frontend/src/pages/group/index.vue`（组局，新）
- `frontend/src/pages/message/index.vue`（消息，新）

**改写（对齐 ref）：**
- `frontend/src/pages/index/index.vue`（首页）
- `frontend/src/pages/publish/index.vue`（发布）
- `frontend/src/pages/mine/index.vue`（我的）
- `frontend/src/pages.json`（5-tab custom tabBar）
- `frontend/src/uni.scss`（红色主题 token）
- `frontend/src/App.vue`（全局样式）

**保留（轻改主题，本期不重写）：**
- post-detail / verify / admin / my-posts / tags

## 7. 关键依赖与风险

- uni-app `tabBar.custom` 跨平台一致性 → 用每页渲染组件 + hideTabBar 双保险，已规避。
- H5 下 rpx 自动换算为 rem，视觉与 mp 一致。
- emoji 在不同平台渲染略有差异 → 可接受（预览阶段）。
- `@/` 别名由 uni-app 插件提供，无需改 vite.config。

## 8. 验收

- `npm run type-check` 0 error
- `npm run dev:h5` 能编译并在浏览器渲染 5 个 tab 页
- `npm run build:mp-weixin` 能编译通过
- 5 页视觉对齐 ref/ 关键区块（头部红、卡片圆角、信息流、组局进度条、消息空态、我的统计面板）
