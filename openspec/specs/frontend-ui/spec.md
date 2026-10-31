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
- **THEN** 全部使用内联 SVG 或 emoji，不引用任何 PNG 图标文件

### Requirement: 玫瑰红品牌主题统一

全站 MUST 使用玫瑰红品牌主题，通过 CSS 变量（设计 token）统一管理，主色值须同时满足「白字压主色 ≥4.5:1」与「主色压白底 ≥4.5:1」。

#### Scenario: 应用主题

- **WHEN** 任意页面渲染头部/按钮/高亮元素
- **THEN** 使用 `--primary: #c2455c` 等 token；旧色 `--brand-red` / `#007aff` / `#1296db` 不再出现在主视觉

#### Scenario: 主色承担填充与文字两种角色

- **WHEN** 主色既作实心按钮底（白字）又作强调文字
- **THEN** 两者都必须达 WCAG AA；不满足时文字改用 `--primary-text`、填充改用 `--primary-fill`

### Requirement: 白天/夜晚双模式

前端 MUST 支持亮色与暗色两套主题，令牌集中在 `App.vue` 的 `page{}` 与 `.theme-dark{}` 两块中，暗色只覆写令牌不改结构。

#### Scenario: 切换主题

- **WHEN** 用户在设置页切换深色模式
- **THEN** 页面根节点加 `.theme-dark` 类，子树令牌随主题生效，H5 同步 `<html>` 类名与原生导航栏底色，选择持久化在本地存储

#### Scenario: 暗色下的品牌小字

- **WHEN** 暗色模式下渲染品牌色小字（链接、标签、按钮文字）
- **THEN** 使用暗色专属的 `--primary-text`（提亮值），在全部暗底上 ≥4.5:1

### Requirement: 图标体系单一来源

图标 MUST 由 `frontend/scripts/gen_icons.py` 统一生成，页面与组件一律通过 `frontend/src/utils/icons.ts` 注册表引用，不得手写路径或使用 emoji。

#### Scenario: 引用图标

- **WHEN** 页面或组件需要某个图标
- **THEN** 从 `ICONS` / `ICON_TONES` 注册表取路径；生成器可完整重跑且产物一致，注册表与磁盘文件一一对应

#### Scenario: 底栏图标

- **WHEN** 渲染底部导航图标
- **THEN** 常态取 default 变体、激活态取品牌色变体（亮色 `primary`、暗色 `primary-dark`，与该模式的 `--primary-text` 同色），路径来自注册表，不指向已删除的旧目录
- **AND** 激活态文字用 `--primary-text`（不用 `--primary`），在亮/暗页底上均 ≥4.5:1，不计入品牌例外

### Requirement: 文本对比度令牌化

正文与标签类文字 MUST 通过令牌取色，色值选择以实测对比度为准，不以观感为准。

#### Scenario: 文本对比度达标

- **WHEN** 渲染文字
- **THEN** 正文对比度 ≥4.5:1、占位符 ≥4.0:1、大字 ≥3:1；深色模式同样达标

#### Scenario: 自动化守护

- **WHEN** 跑 `frontend/scripts/ui-contrast-audit.py`
- **THEN** 对比度按祖先链合成实色层与线性渐变（取元素位置的实际 alpha，底色未知处按最坏情况取下界）后判定，不达标项必须清零

#### Scenario: 管理台同口径

- **WHEN** 渲染管理台（Element Plus）文字与输入框占位符
- **THEN** 颜色一律取自 `admin-frontend/src/styles/theme.css` 令牌，不得回退到组件库默认色（默认占位符 `#a8abb2` 在白底上仅 2.30:1，必须覆写）；由 `admin-frontend/scripts/ui-walkthrough.py` 断言输入框占位符 ≥4.5:1

### Requirement: 可点击控件最小点击区

所有真实可点击控件 MUST 具备不小于 32×32px 的点击区，不得仅靠小图标本身承载点击。

#### Scenario: 图标型操作入口

- **WHEN** 控件以图标承载交互（点赞、收藏、更多、返回、筛选胶囊等）
- **THEN** 通过内边距或最小尺寸把点击区扩到 ≥32×32px，图标视觉尺寸保持不变

#### Scenario: 审计判定可点击元素

- **WHEN** 自动化审计扫描点击区
- **THEN** 以元素是否真正绑定事件监听判定（Vue 的 `Symbol(_vei)`），而非按类名猜测；装饰性图标与信息性文本不计为缺陷

### Requirement: 最小字号下限

正文与徽标类文字 MUST 不小于 22rpx（390px 宽下约 11.4px），底栏标签不小于 22rpx。

#### Scenario: 徽标与角标渲染

- **WHEN** 渲染热榜徽标、置顶/精华标签、计数角标、广告角标
- **THEN** 字号不小于 22rpx，自动化审计中无小于 11px 的可见文字

### Requirement: 不可控底色上的文字须有暗化保障层

当文字落在照片、渐变或后台下发颜色之上时 MUST 叠加暗化层，禁止依赖底色恰好够深。

#### Scenario: 广告位轮播

- **WHEN** 渲染首页广告位（图片 banner 或纯色渐变 banner）
- **THEN** 文字与图标位于暗化层之上，图片 banner 的暗化集中在标题区、纯色 banner 的暗化集中在文案区；角标自带深色底，最坏情况下白字对比度仍 ≥4.5:1

### Requirement: 走查断言基于令牌而非色值

UI 走查脚本 MUST 断言元素的实际对比度或令牌一致性，不得把断言写死在具体色值上。

#### Scenario: 令牌调整后断言仍成立

- **WHEN** 设计令牌取值调整（如换品牌主色、调整暗色文字）
- **THEN** 走查断言按实测对比度阈值或读取令牌计算值判定并继续成立，无需同步维护硬编码色值列表

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

