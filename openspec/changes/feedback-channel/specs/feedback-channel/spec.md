# 反馈通道规范

## ADDED Requirements

### Requirement: 内部测试反馈提交

系统 SHALL 提供反馈提交入口，登录用户可直接提交；未登录者 SHALL 需要提供内部测试口令。
系统 SHALL 记录反馈的类型、严重程度、标题、描述与提交时刻的页面环境信息，
并且 SHALL NOT 在任何反馈响应中包含真实姓名或学号。

#### Scenario: 登录用户提交反馈

- **WHEN** 已登录用户在电脑端或 H5 端提交一条反馈
- **THEN** 系统 SHALL 创建反馈记录并返回反馈编号
- **AND** 系统 SHALL 记录提交人的昵称，但响应中 SHALL NOT 出现真实姓名或学号

#### Scenario: 未登录用户凭内部口令提交

- **WHEN** 未登录用户填写了正确的内部测试口令并提交反馈
- **THEN** 系统 SHALL 接受该反馈并返回反馈编号
- **AND** 系统 SHALL 把用户填写的昵称记为反馈来源标识

#### Scenario: 未登录用户口令缺失或错误

- **WHEN** 未登录用户未填写口令或填写了错误的口令
- **THEN** 系统 SHALL 拒绝该提交并返回明确的鉴权失败提示
- **AND** 当服务端未配置内部测试口令时，系统 SHALL 关闭免登录提交路径

### Requirement: 反馈附件与现场信息

系统 SHALL 支持为反馈上传截图，并 SHALL 支持随反馈附带客户端诊断信息。
截图 SHALL 存放在独立于公开媒体体系的私有目录中，只有管理台鉴权接口 SHALL 能读取。

#### Scenario: 上传反馈截图

- **WHEN** 反馈创建成功后，用户上传一张截图
- **THEN** 系统 SHALL 将图片归一化后写入私有目录并在反馈记录中登记
- **AND** 系统 SHALL 拒绝非图片文件、超过 5MB 的图片，以及超过 5 张的截图
- **AND** 系统 SHALL NOT 把该图片置为任何公开可访问状态

#### Scenario: 未授权用户上传截图

- **WHEN** 一个既不是反馈提交者、又没有该反馈上传令牌的请求尝试上传截图
- **THEN** 系统 SHALL 拒绝该请求

#### Scenario: 随反馈附带诊断信息

- **WHEN** 用户在提交反馈时开启「附带诊断信息」
- **THEN** 系统 SHALL 一并提交客户端采集的页面报错、失败请求、当前路由与浏览器环境
- **AND** 客户端 SHALL 只在内存中保留这些诊断记录，页面刷新后 SHALL 清空

### Requirement: 反馈的接收与处理

系统 SHALL 提供管理台接口供负责人查看与处理反馈，状态流转 SHALL 覆盖待处理、处理中、
已解决与已关闭，且状态变更 SHALL 记入管理操作日志。

#### Scenario: 管理台查看反馈列表

- **WHEN** 负责人打开管理台反馈箱
- **THEN** 系统 SHALL 返回反馈列表、总数与按状态与类型筛选的能力
- **AND** 系统 SHALL 展示未处理反馈的数量

#### Scenario: 管理台查看反馈详情与截图

- **WHEN** 负责人查看某条反馈的详情
- **THEN** 系统 SHALL 返回完整描述、页面环境信息与诊断日志
- **AND** 系统 SHALL 允许负责人查看该反馈的截图

#### Scenario: 未鉴权访问管理端反馈接口

- **WHEN** 未携带有效管理台凭证的请求访问反馈管理接口
- **THEN** 系统 SHALL 拒绝该请求

### Requirement: 反馈的快速送达

系统 SHALL 支持把新反馈推送到外部 Webhook，使负责人无需登录后台即可收到。
推送 SHALL 支持通用、飞书与企业微信三种载荷格式；推送失败 SHALL NOT 影响反馈入库。

#### Scenario: 提交后推送到飞书机器人

- **WHEN** 配置了 `FEEDBACK_WEBHOOK_URL` 且 `FEEDBACK_WEBHOOK_KIND` 为 `feishu`，
  此时有用户提交反馈
- **THEN** 系统 SHALL 向该地址推送一条包含类型、严重程度、描述与诊断摘要的文本消息

#### Scenario: 推送失败

- **WHEN** Webhook 地址不可达或超时
- **THEN** 系统 SHALL 记录失败日志
- **AND** 反馈记录 SHALL 仍然正常保存并可在管理台看到

#### Scenario: 未配置 Webhook

- **WHEN** `FEEDBACK_WEBHOOK_URL` 为空
- **THEN** 系统 SHALL 正常保存反馈且不发起任何推送
