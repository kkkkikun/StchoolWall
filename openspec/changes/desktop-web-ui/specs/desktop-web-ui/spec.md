# 电脑端 Web UI 规范

## ADDED Requirements

### Requirement: 电脑端信息流浏览

系统 SHALL 为电脑浏览器提供独立于移动端的信息流页面，支持推荐、最新、热门、精华四种视角，
列表使用游标分页并提供加载更多。

#### Scenario: 打开首页看到推荐流

- **WHEN** 用户在电脑浏览器打开电脑端首页
- **THEN** 页面 SHALL 展示推荐流帖子列表，每条含作者、内容摘要、图片、标签与互动计数
- **AND** 页面 SHALL 提供切换到最新、热门、精华的入口

#### Scenario: 帖子列表加载更多

- **WHEN** 后端返回 `has_more` 为真且用户点击加载更多
- **THEN** 系统 SHALL 用上一次返回的游标请求下一页并追加到列表末尾
- **AND** 系统 SHALL 在没有更多数据时隐藏加载更多按钮

### Requirement: 电脑端登录与会话

系统 SHALL 支持电脑端注册与登录，访问令牌只保存在内存中；
刷新通道 SHALL 依据页面是否为安全上下文自动选择，且 SHALL NOT 因部署形态不同而需要改代码。

#### Scenario: 注册新账号

- **WHEN** 用户提交 2–20 位登录名与不少于 10 位的密码
- **THEN** 系统 SHALL 调用注册接口并在成功后建立会话
- **AND** 当两次输入的密码不一致或长度不合规时，系统 SHALL 在发起请求前提示用户

#### Scenario: 刷新页面后恢复会话

- **WHEN** 用户已登录并刷新页面
- **THEN** 系统 SHALL 通过刷新通道换回新的访问令牌并恢复登录态
- **AND** 系统 SHALL NOT 把访问令牌写入 localStorage

#### Scenario: 纯 HTTP 部署下的刷新通道

- **WHEN** 页面运行在非安全上下文（HTTP）
- **THEN** 系统 SHALL 使用客户端类型 `native` 并把刷新令牌放进刷新请求体
- **AND** 系统 SHALL NOT 依赖带 `Secure` 属性的 cookie

### Requirement: 电脑端发帖与互动

系统 SHALL 支持在电脑端发布帖子、发表评论、点赞、收藏与关注；
发布带图时 SHALL 通过上传接口取得 `media_id` 后随发帖提交。

#### Scenario: 发布带图帖子

- **WHEN** 用户选择图片并提交帖子
- **THEN** 系统 SHALL 先上传图片取得 `media_id`，再以 `media_ids` 字段创建帖子
- **AND** 系统 SHALL NOT 同时提交 `images` 字段

#### Scenario: 未登录用户尝试互动

- **WHEN** 未登录用户点击点赞、收藏、评论或发布
- **THEN** 系统 SHALL 引导其前往登录页，并在登录后回到原页面

#### Scenario: 账号没有发布权限

- **WHEN** 已登录账号的角色不满足发布要求
- **THEN** 系统 SHALL 在发布页提示需要完成学生身份认证
- **AND** 系统 SHALL NOT 把普通无权限错误直接抛给用户

### Requirement: 电脑端界面规范

电脑端界面 SHALL 使用语义化设计令牌管理颜色、间距、字号与圆角，
SHALL 支持亮/暗双模式，且暗色模式只覆写令牌不改结构。

#### Scenario: 主题切换

- **WHEN** 用户在顶部导航切换暗色模式
- **THEN** 系统 SHALL 仅通过覆写令牌切换整个界面配色
- **AND** 系统 SHALL 把选择持久化到本地存储，刷新后仍然生效

#### Scenario: 文本对比度

- **WHEN** 渲染正文、占位符或图片上的文字
- **THEN** 对比度 SHALL 不低于规范要求（正文 ≥4.5:1，占位符 ≥4.0:1，大字 ≥3:1）
- **AND** 图片上的文字 SHALL 叠加暗化层以保证最坏情况下的对比度

### Requirement: 电脑端构建与门禁

电脑端 SHALL 与仓库内其他前端同等参与 CI 门禁，其接口调用 SHALL 纳入接口契约漂移守卫。

#### Scenario: 接口漂移守卫覆盖电脑端

- **WHEN** 后端接口发生变化而电脑端仍在调用已不存在的路径
- **THEN** `frontend/scripts/api-contract-check.mjs` SHALL 以非零退出码失败
- **AND** 该脚本 SHALL 扫描 `desktop-frontend/src/api` 下的顶层 `.ts` 文件

#### Scenario: 电脑端构建参与流水线

- **WHEN** 仓库流水线运行 Production CI
- **THEN** 电脑端 SHALL 依次执行类型检查、单元测试、构建与依赖高危审计
- **AND** 发布制品 SHALL 包含 `web/pc/` 目录
