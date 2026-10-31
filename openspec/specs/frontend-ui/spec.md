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

### Requirement: 账号登录/注册独立页

前端 MUST 提供独立账号页 `pages/auth/index` 承载登录、注册与找回密码三种模式，取代原「我的」页内的登录弹窗。

#### Scenario: 进入账号页

- **WHEN** 未登录用户在「我的」页点击「登录 / 注册」
- **THEN** 跳转独立账号页 `pages/auth/index`，页面自带返回入口；宽屏（桌面 H5）下表单最大宽度 480px 居中，不拉满整屏

#### Scenario: 三模式切换

- **WHEN** 用户在账号页切换「登录 / 注册」标签或点击「忘记密码」
- **THEN** 分别进入登录、注册、找回密码模式，主按钮文案与输入项随之变化（登录 2 项、注册 2 项、找回 3 项含找回码）；请求在途期间模式切换被锁定

#### Scenario: 提交防重复与错误就地提示

- **WHEN** 用户提交账号表单
- **THEN** 请求在途期间忽略重复点击并置 saving 视觉态；输入校验失败、接口错误与网络异常都以页内就地提示呈现，不弹 toast 打断输入；登录成功后退回来源页

#### Scenario: 会话响应契约校验

- **WHEN** 登录/注册接口返回缺少 `access_token` / `role` / `user_info` 或 `role` 越界的响应
- **THEN** 不落地会话、不写入用户信息，展示「登录响应异常，请稍后重试」

### Requirement: Mock 数据独立预览

前端 MUST 在无后端的情况下独立预览，所有页面数据来自本地 mock。

#### Scenario: 脱离后端运行

- **WHEN** 后端未启动
- **THEN** 5 个 tab 页仍能正常渲染全部区块与样例数据

### Requirement: 文本对比度令牌化

前端 MUST 通过设计令牌保证正文对比度达标，禁止把不达标的颜色硬编码进组件。

#### Scenario: 暗色模式辅助文字

- **WHEN** 暗色模式下渲染 meta、时间、浏览数等辅助文字
- **THEN** 使用 `--text-3`（深底 ≥4.5:1），不得使用低对比灰（如 `#71767b` 在 `#16181c` 上仅 3.88:1）

#### Scenario: 蓝色小字与蓝底白字

- **WHEN** 渲染蓝色小字链接/数字，或蓝色底 + 白色文字的徽章
- **THEN** 蓝色小字用 `--primary-text`（亮色 `#0d74ab` 白底 5.12:1 / 暗色 `#4ba3e3` 全部暗底 ≥5.35:1），蓝底白字徽章用 `--primary-badge`（白字 5.48:1）；仅品牌主按钮与底栏激活态保留 X 蓝 `#1d9bf0`（3.0:1，已作为既定例外单独计数）

#### Scenario: 占位符与榜单色

- **WHEN** 渲染输入占位符、榜单第 2/3 名序号、收藏态文字
- **THEN** 占位符 ≥4.0:1；榜单金/铜与收藏文字在亮色下 ≥4.5:1、暗色下同样达标，不使用 `#ffd400`（白底仅 1.43:1）这类低对比色

#### Scenario: 头像首字

- **WHEN** 渲染无头像用户的首字占位
- **THEN** 首字用 `--on-avatar` 深墨而非白色（白字在浅色头像底上仅 1.2~1.6:1），全调色板最差对比度 ≥8:1

### Requirement: 头像配色唯一来源

头像底色与首字前景色 MUST 只有一处实现。

#### Scenario: 同一昵称跨页一致

- **WHEN** 同一昵称在信息流、详情、个人主页、消息、设置等页面出现
- **THEN** 头像底色一致，均由 `frontend/src/utils/avatar.ts` 的 `avatarColor()` 计算，不得在页面内各自维护调色板

### Requirement: 横向滚动行渐隐

横向滚动的分类/筛选行 MUST 在容器边缘做渐隐，不得把胶囊从字形中间硬切。

#### Scenario: 滚到端点

- **WHEN** 横向滚动行内容超出容器宽度
- **THEN** 内容被裁切的一侧显示渐隐覆盖层（小程序不支持 CSS mask，用绝对定位渐变层实现），滚动到该端点时对应侧渐隐消失；末尾项可完整滚动至可见

### Requirement: 未登录态不展示个人内容

未登录时 MUST 不展示需要登录才能产生的数据入口。

#### Scenario: 未登录进入「我的」页

- **WHEN** 未登录用户进入「我的」页
- **THEN** 不展示「编辑资料」按钮与「我发出的内容 / 评论 / 收藏 / 点赞」四个个人内容 Tab，改为登录引导说明；登录后恢复个人内容 Tab 与「编辑资料」

### Requirement: 卡片类型标识为紧凑标签

卡片上的类型标识 MUST 为标题行内的紧凑标签，不得使用贯穿卡片全高的饱和色块。

#### Scenario: 渲染组局卡片

- **WHEN** 渲染组局/拼单卡片
- **THEN** 类型以小色块标签（组局 / 拼单）置于标题左侧，标签文字对比度 ≥4.5:1

### Requirement: 走查断言基于对比度而非色值

UI 走查脚本 MUST 断言元素的实际对比度，不得把断言写死在具体色值上。

#### Scenario: 令牌调整后断言仍成立

- **WHEN** 设计令牌取值调整（如暗色次级文字提亮）
- **THEN** 走查断言按实测对比度阈值判定并继续成立，无需同步维护硬编码色值列表

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

### Requirement: 白字填充面使用达 AA 的蓝色

承载白色文字的填充面（主按钮、卡片、标签）MUST 使用 `--primary-fill` 系列令牌，不得直接使用品牌蓝 `#1d9bf0`。

#### Scenario: 主按钮渲染

- **WHEN** 渲染发布/组局/登录/申诉等主按钮
- **THEN** 底色为 `--primary-fill`（白字 5.48:1）或其渐变变体，达到 WCAG AA；品牌蓝 `#1d9bf0` 仅保留用于非文字强调（图标、下划线、描边、底栏激活图标）

