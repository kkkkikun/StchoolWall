# Post Images — 发布页图片全流程

## Why

发布页「添加照片」是假按钮（toast"开发中"），发帖无法带图——而帖子图片的**后端链路已全部就绪**（`/upload/direct?kind=posts` 服务端生成路径 + `PostCreate.images` 校验 `/static/` 前缀 + 审核管线 img_sec_check 接口 + 详情页/信息流图片渲染网格与预览）。唯一缺口在前端发布页。

用户已确认范围（2026-09-05）：只做发布页图片（最小）；隐藏「添加视频」假按钮（后端无视频支持）；顺手修复 `post-card` 引用 `/static/default-avatar.png`（目录）导致 dev server EISDIR 崩溃的技术债。

## What Changes

- 发布页：`chooseImage`（多选、≤6 张、compressed）→ 逐张 `uploadFile(kind='posts')` → 已选图片网格（删除/失败重试）→ `createPost` 携带 images
- 隐藏「添加视频」按钮
- `post-card.vue`：无头像时渲染首字符色块（与个人主页同风格），移除对不存在文件的引用
- 后端零改动

## Impact

- `frontend/src/pages/publish/index.vue`（图片状态机与网格 UI）
- `frontend/src/components/post-card.vue`（头像兜底）
- 纯前端，E2E 验证（后端 420 tests 不动）
