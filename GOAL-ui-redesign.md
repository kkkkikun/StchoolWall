# GOAL：SchoolWall（鄂应墙）UI/UX 整体重设计 —— 三套主题 × 三个分支

> 本文件是自包含任务书。执行者不依赖任何会话上下文，从头读完即可开工。
> 项目根目录：`/home/kikun/MyProject/SchoolWall`

---

## 1. 使命

为 SchoolWall 项目完成 **三套风格迥异、完整可交付的 UI 重设计**，每套主题独立一个 git 分支，统一覆盖两端：

| 范围 | 目录 | 技术栈 | 说明 |
|------|------|--------|------|
| 学生端 | `frontend/` | uni-app（Vue3 + TS + Vite5 + scss） | 微信小程序为主 + H5 预览，含全部页面与组件 |
| 管理后台 | `admin-frontend/` | Vue3 + Element Plus + Pinia + ECharts | 独立 Web 管理端，含登录页/布局/全部视图 |

**约束：`main` 分支保持不动**；三套主题分别落在三个新分支上；后端 `backend/`、`openspec/` 一律不改。

---

## 2. 环境事实（已核实）

- 后端 FastAPI 已运行：`http://localhost:8000`（`GET /health` → `{"status":"ok"}`）
- 学生端 H5 dev server 已运行：`http://localhost:5173`（`npm run dev:h5`，`/api` 代理到 8000）
- 管理后台 dev server 已运行：`http://localhost:5174`（`npm run dev`，`/api`、`/static` 代理到 8000）
- git 工作区干净，当前在 `main`；远程为 `origin`
- 数据库/Redis 走 `docker-compose.yml`，与 UI 任务无关，不要动

### 页面清单（重设计必须全覆盖）

**学生端 `frontend/src/pages/`**：index（首页信息流）、group（组局/攒局）、publish（发布）、message（消息通知）、mine（我的）、post-detail（帖子详情）、search（搜索）、verify（学籍认证）等，以 `src/pages.json` 实际注册为准。公共组件在 `src/components/`（feed-card 信息流卡片、tab-bar 自定义底部导航、ui-icon 图标等）。全局样式入口：`App.vue` 的全局 style + `uni.scss`。

**管理后台 `admin-frontend/src/views/`**：看板 dashboard（统计卡 + ECharts 趋势线）、帖子、用户、举报、轮播广告、评论、组局、公告、操作日志、登录页。布局组件（侧边栏/顶栏/主区域）+ `src/components/` 公共组件 + 全局样式入口（`main.ts` 引入的全局 css）。

---

## 3. 三套设计方向（可微调细节，但三套必须风格差异明显）

### 主题 A ——「校园清新」（分支名 `ui/theme-a-fresh`）
- 气质：奶油白/米杏底色，樱花粉 + 青提绿 + 天空蓝点缀，像校园手账
- 特征：大圆角（16~24rpx 级别卡片再大）、柔和弥散阴影、渐变点缀、贴纸感标签、圆润字体层级
- 管理后台：浅色侧边栏 + 彩色高亮当前项，卡片化统计，图表用柔和多色

### 主题 B ——「夜间霓虹」（分支名 `ui/theme-b-neon`）
- 气质：深色玻璃拟态（glassmorphism）+ 霓虹渐变（紫→青、品红点缀），科技潮流感
- 特征：深底（#0f1115 级）、半透明毛玻璃卡片、霓虹描边/发光强调、高对比文字
- 管理后台：深色控制台风（类 Vercel/Linear），图表用霓虹色系，表格深色适配

### 主题 C ——「极简杂志」（分支名 `ui/theme-c-editorial`）
- 气质：白底黑字、编辑部/杂志排版，克制的单强调色（如墨绿或砖红）
- 特征：强排版层级（大标题、衬线感标题可用系统字体加粗+字距）、细分隔线、无阴影或极浅阴影、直角或小圆角、大量留白
- 管理后台：类 Notion/Stripe 极简风，细线框表格，图表单色系 + 单强调色

每套主题要求：

1. **设计令牌集中化**：色彩/圆角/阴影/间距/字号全部收敛到统一位置——学生端在 `uni.scss` + `App.vue` 全局 CSS 变量；管理后台用 Element Plus CSS 变量覆盖（`--el-color-primary` 系列）+ 全局样式文件。页面里不再散落硬编码颜色（把现有硬编码颜色替换为令牌引用）。
2. **组件全状态覆盖**：按钮（默认/按下/禁用）、输入框（聚焦/错误）、卡片、弹窗、标签、空态、加载态、骨架屏或 loading 样式，两端都要有。
3. **管理后台重点**：登录页、整体布局（侧边栏/顶栏）、表格、ECharts 配色随主题（图表硬编码颜色要改）、弹窗、分页、消息提示。
4. **学生端重点**：自定义 tab-bar、信息流卡片、发布页、帖子详情、我的页、认证页。

---

## 4. 硬性红线（违反即返工）

1. **不改业务逻辑**：不动 `<script>` 中的请求、状态流转、API 封装、路由跳转参数；只动样式、模板结构中的纯展示部分（class/布局结构可以调整）。
2. **uni-app 小程序兼容**：样式要兼容 mp-weixin——用 rpx；避免 `*` 通配选择器、避免 `:nth-child` 之外的高级伪类组合；背景图用网络图或 static 资源而非本地绝对路径；改完必须保证 `npm run build:h5` 通过（小程序端如有条件也要验证不报错）。
3. **不破坏功能**：改完每端跑 `npm run type-check`（学生端）/构建，报错清零才算完。
4. **不改后端、不改接口、不改 pages.json 的路由注册**（globalStyle/tabBar 的颜色配置属于 UI，可以改）。
5. **不提交 node_modules / dist / 日志**；不执行 `git push`（除非用户明确要求）。
6. 提交信息风格沿用仓库惯例：中文、`feat(模块): 描述` 格式。

---

## 5. 执行流程（按顺序）

1. **探索**：通读两端样式体系（`frontend/src/App.vue`、`uni.scss`、`pages.json`、`components/`；`admin-frontend/src/` 的全局样式、布局组件、`views/` 清单），列出所有含硬编码颜色的文件清单。
2. **建分支**：从 `main` 依次创建 `ui/theme-a-fresh`、`ui/theme-b-neon`、`ui/theme-c-editorial`（三个分支互相独立，都基于 main）。
3. **逐分支实施**（一个分支完整做完再开下一个）：
   - a. 先落设计令牌（学生端：`uni.scss` + App.vue CSS 变量；管理后台：Element Plus 变量覆盖 + 全局 css）
   - b. 学生端：App.vue 全局样式 → 组件（tab-bar/feed-card/ui-icon）→ 逐页覆盖
   - c. 管理后台：全局变量与布局（侧边栏/顶栏）→ 登录页 → 各视图（表格/图表/弹窗）→ ECharts 配色
   - d. 验证：两端 type-check / build 通过；用浏览器打开 :5173 与 :5174 截图走查主要页面（首页、详情、发布、我的；登录、看板、帖子列表），发现问题当分支内修完
   - e. 提交：该分支 1~3 个语义化 commit（学生端/管理后台/文档可分开）
4. **收尾汇报**：汇报三个分支名、commit 列表、每套主题的截图结论与切换方式（`git checkout ui/theme-a-fresh` 后 dev server 热更新即可预览）。

---

## 6. 验收清单（每套主题都过一遍才算完成）

- [ ] 学生端所有注册页面均已适配主题（无残留旧配色突兀页）
- [ ] 管理后台登录页 + 布局 + 全部视图适配主题
- [ ] ECharts 图表配色与主题一致（看板页肉眼检查）
- [ ] 颜色/圆角/阴影收敛到设计令牌，无大面积硬编码色残留（grep 抽查）
- [ ] 学生端 `npm run type-check` 0 报错；`npm run build:h5` 成功
- [ ] 管理后台 `npm run build`（vite build）成功
- [ ] 浏览器截图走查通过：无文字被截断、无对比度不足、无布局塌陷（尤其深色主题的输入框/表格/弹窗）
- [ ] 该分支已提交，工作区干净；`main` 无任何改动

---

## 7. 备注与建议

- 管理后台 Element Plus 若为全量引入，直接全局 CSS 变量覆盖最稳；同时给 `html.dark` 或 body 级类名留主题作用域。
- 学生端若 `uni.scss` 已有变量，优先沿用变量名、改值，减少散弹式修改。
- 截图用无头浏览器或 ZCode 的 browser-use 能力；管理后台登录账号不存在时，只截图登录页即可，不强求登录进去。
- 三套主题可并行推进（三个工作树 `git worktree` 更快），但提交前必须逐分支独立验证。
