# Tasks: 前端 UI/UX 大改造

> 状态：✅ 全部完成并通过验证（2026-07-06）。变更待用户预览确认后再 archive。

## A. 设计基础（先做，被所有页面依赖）

- [x] A1. `uni.scss` 红色主题 token + `App.vue` 全局样式（CSS 变量、page 背景）
- [x] A2. `components/ui-icon.vue` 图标组件（Unicode/emoji 字形，跨平台；放弃内联 SVG——mp-weixin 不支持）
- [x] A3. `components/tab-bar.vue` 自定义底栏（5 项，reLaunch 切换，current 高亮）
- [x] A4. `utils/mock.ts` + `types/mock.ts` 全部 ref 样例数据

## B. 五个主 tab 页

- [x] B1. `pages/index/index.vue` 首页：红头搜索+签到 / 通知马灯 / 十大热帖 / 金刚区 10 格 / Banner / 吸顶分类 Tab / 信息流卡片 / 悬浮搜索
- [x] B2. `pages/group/index.vue` 组局：累计统计 / Banner / 双动作卡 / 10 分类筛选 / 组局卡片（类型标+进度条）/ 悬浮搜索
- [x] B3. `pages/publish/index.vue` 发布：热搜标签 / 版块选择 / 正文+垂直工具栏 / 图片视频槽 / AI 开关 / 底部红按钮
- [x] B4. `pages/message/index.vue` 消息：红头 / 4 类通知圆（角标）/ 帖子动态+全部已读 / 空态"暂无消息"
- [x] B5. `pages/mine/index.vue` 我的：红头（头像/昵称/学校胶囊）/ 4 列统计 / 菜单分组（负 margin 上浮覆盖）

## C. 路由与配置

- [x] C1. `pages.json`：5 主页面注册，移除原生 tabBar（改自研 reLaunch 方案）
- [x] C2. 顺带修复既有 type 错误（非本次引入，但阻塞 type-check）：admin.ts 误导入 Report、request.ts data 类型、storage.ts UserInfo.id、admin/index.vue 的 require→ESM import

## D. 验证（Gate 5）

- [x] D1. `npm run type-check` → exit 0（0 error）
- [x] D2. `npm run build:h5` → DONE Build complete
- [x] D3. `npm run build:mp-weixin` → DONE Build complete
- [x] D4. H5 dev server → http://localhost:5173/ 返回 HTTP 200，5 个 tab 可切换预览

## 备注

- 二级页（post-detail/verify/admin/my-posts/tags）未重写，仅 admin 顺带修了 require；这些页仍是旧蓝色主题，待后续推进时统一红色化。
- 图标全部用 emoji/Unicode，未生成 PNG；生产图标资源后续单独补。
- 数据全部 mock，未接真实后端。
