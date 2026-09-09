# Post Images Spec Delta

## ADDED Requirements

### Requirement: 发布页图片上传

发布页 MUST 支持选图（一次最多补足至 6 张、compressed）、逐张上传至 kind=posts、已选网格预览（删除/失败重试），发帖请求 MUST 仅携带上传完成的 `/static/posts/` URL。

#### Scenario: 正常带图发布
- **WHEN** 登录学生在发布页选 3 张图并发布
- **THEN** 帖子 images 为 3 个 /static/posts/ URL，详情页渲染 3 图网格，点图可全屏预览

#### Scenario: 上限控制
- **WHEN** 已选 6 张后再点添加
- **THEN** 提示上限不可再选（chooseImage count 按剩余额度）

#### Scenario: 上传失败可恢复
- **WHEN** 某张上传失败
- **THEN** 该格显示失败态，可重试或删除；不影响其余图片

#### Scenario: 未完成禁止提交
- **WHEN** 仍有图片处于上传中/失败态时点发布
- **THEN** 阻止提交并提示等待或处理失败图片

### Requirement: 无视频入口

发布页 MUST NOT 展示「添加视频」入口（后端无视频支持）。

#### Scenario: 页面无视频入口
- **WHEN** 打开发布页
- **THEN** 不存在「添加视频」按钮，仅「添加照片」

### Requirement: 头像兜底不引用缺失文件

post-card 组件在作者无头像时 MUST 渲染昵称首字符色块，MUST NOT 引用 /static/default-avatar.png（该路径为目录，引用触发 dev server EISDIR）。

#### Scenario: 无头像作者的内容卡
- **WHEN** 渲染无头像作者的帖子卡
- **THEN** 显示昵称首字符 + 哈希色圆形色块，无 /static/default-avatar.png 网络请求
