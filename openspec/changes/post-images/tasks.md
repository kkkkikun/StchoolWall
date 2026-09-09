# Tasks — Post Images

> 后端已就绪零改动；前端 TDD 以 E2E 实证代替单测（项目无前端测试基建）。

## 批1 发布页图片
- [x] 图片状态机：待上传(本地临时路径)→上传中→完成(/static/ url)→失败(可重试/可删)；上限 6 张
- [x] chooseImage(count=剩余额度, sizeType=compressed) + 逐张 uploadFile(kind='posts')
- [x] 已选网格 UI：缩略图 + 删除角标 + 失败红标重试；「添加照片」格随剩余额度显隐
- [x] 提交校验：有图片仍在传时阻止发布；images 仅含已完成 url
- [x] 隐藏「添加视频」按钮
- [x] E2E：拦截 filechooser 传 2 图 → 发布 → DB images 落 2 个 /static/posts/ url → 详情页渲染网格 → 点图预览

## 批2 post-card 头像兜底
- [x] 移除 `/static/default-avatar.png` 引用，无头像渲染首字符色块（colorOf 同款哈希色）
- [x] my-posts / mine / profile 三页面回归截图无 404 资源；vue-tsc 0 错

## 收尾
- [x] 全量后端回归（确认零影响）+ SNAPSHOT/tasks 同步；提交等用户确认
