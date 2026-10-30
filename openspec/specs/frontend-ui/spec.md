# frontend-ui Specification

## Purpose
TBD - created by archiving change frontend-redesign. Update Purpose after archive.
## Requirements
### Requirement: 五 Tab 导航架构

前端 MUST 提供底部 5 个 tab：首页 / 组局 / 发布 / 消息 / 我的，通过自定义 tabBar 组件切换。

#### Scenario: 切换 tab

- **WHEN** 用户点击底栏某 tab
- **THEN** 通过 `uni.switchTab` 切换到对应页面，当前 tab 图标与文字高亮为品牌红 `#f73b43`

#### Scenario: 无 PNG 依赖

- **WHEN** tabBar 与各页面渲染图标
- **THEN** 全部使用 SVG 图标资源（`static/icons/**.svg`，经 `<image mode="aspectFit">` 引用），不引用任何 PNG 图标文件，也不使用 emoji 字形

#### Scenario: 图标资源统一生成

- **WHEN** 需要新增或调整图标
- **THEN** 图标几何只在 `frontend/scripts/gen_icons.py` 中维护并生成到 `static/icons/<分组>/`，语义名与色调变体登记在 `frontend/src/utils/icons.ts`（生成物，勿手改）；手写 SVG 与 emoji 字形都不得进入模板

### Requirement: 红色品牌主题统一

全站 MUST 使用红色品牌主题，通过 CSS 变量（设计 token）统一管理。

#### Scenario: 应用主题

- **WHEN** 任意页面渲染头部/按钮/高亮元素
- **THEN** 使用 `--brand-red: #f73b43` 等 token，旧蓝色 `#007aff` / `#1296db` 不再出现在主视觉

### Requirement: 首页信息流与运营位

首页 MUST 还原 ref/首页 设计：红色搜索签到头、通知马灯、十大热帖、金刚区 10 格、Banner、吸顶分类 Tab、信息流卡片、悬浮搜索。

#### Scenario: 渲染信息流

- **WHEN** 首页加载
- **THEN** 用 mock 数据渲染信息流卡片（头像/昵称/认证标/正文/话题/转发收藏赞评论四操作）

### Requirement: 组局页进度条与筛选

组局页 MUST 展示组局/拼单卡片，含报名进度条与分类筛选。

#### Scenario: 计算进度

- **WHEN** 渲染组局卡片
- **THEN** 进度条宽度按 `joined/total*100%` 动态计算，超过总量不变红

### Requirement: 发布页表单与校验

发布页 MUST 提供热搜标签、版块选择、正文输入、媒体上传槽、AI 开关与发布按钮。

#### Scenario: 空提交拦截

- **WHEN** 用户未选版块或正文为空时点击发布
- **THEN** 用 `uni.showToast` 提示具体原因，不发请求

### Requirement: 消息页空态

消息页 MUST 在无动态时渲染"暂无消息"空态。

#### Scenario: 默认空态

- **WHEN** dynamicMessages 为空
- **THEN** 居中显示"暂无消息"；4 类通知圆角标仍展示

### Requirement: 我的页统计面板

我的页 MUST 展示红色沉浸式头部、4 列统计（帖子/评论/收藏/足迹）与分组菜单。

#### Scenario: 渲染统计

- **WHEN** 进入我的页
- **THEN** 头像、昵称、学校胶囊、4 列统计数字、两组菜单卡片均从 mock 渲染，菜单区以负 margin 上浮覆盖红头

### Requirement: Mock 数据独立预览

前端 MUST 在无后端的情况下独立预览，所有页面数据来自本地 mock。

#### Scenario: 脱离后端运行

- **WHEN** 后端未启动
- **THEN** 5 个 tab 页仍能正常渲染全部区块与样例数据

