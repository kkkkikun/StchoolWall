# 内部测试反馈通道（feedback-channel）

## Why

校园墙目前没有面向内部测试人员的反馈入口。测试人员遇到问题时只有两条路：

- 在群里发文字描述 —— 丢失现场，负责人无法复现，UI 问题更是说不清；
- 自己截图再手写路径 —— 反馈与出错那一刻的现场脱节。

问题在于「当时的现场」恰好是最有价值的诊断信息：哪个接口失败了、控制台报了什么错、
当时在哪个页面、什么浏览器与视口。纯文字反馈拿不到这些，负责人只能反复追问，
反馈周期被拉长。

同时，仓库此前**没有任何对外推送通道**（无 webhook / 邮件 / 机器人），
反馈即使提交了也只能靠人工登录后台查看，不具备「快速到达」的能力。

## What Changes

- **新增反馈数据模型 `feedbacks` 表**（Alembic 迁移 `d4e6f8a1b357`）：
  类型、严重程度、标题、描述、页面 URL、路由、视口、主题、端标识、User-Agent、
  客户端 IP、诊断 JSON、截图清单、状态流转（open / handling / resolved / closed）、处理备注。
- **新增反馈接口**（`/api/v1/feedback`）：
  - `POST /feedback` 创建反馈，登录用户直接开放；未登录者需提供内部测试口令；
  - `POST /feedback/{id}/screenshot` 上传截图（单文件，最多 5 张、每张 ≤5MB）；
  - `GET /feedback/mine` 查看自己提交的反馈。
  - 提交分两步（先建记录拿到上传令牌、再传截图），使 H5 端的 `uni.uploadFile`（单文件）
    与电脑端可以共用同一套接口。
- **截图走独立私有目录** `private-feedback/`，**不进公开媒体体系**（`media_assets`）：
  截图可能包含测试人员的环境信息，只有管理台鉴权接口能读取；
  复用媒体归一化逻辑把图片重编码为 JPEG，顺带抹掉 EXIF 里的拍摄信息。
- **新增管理端接口**（`/api/v1/admin/feedback`）：列表、统计、详情、截图读取、状态流转，
  状态变更记入管理操作日志。
- **新增通用 Webhook 推送**：提交后异步推送到 `FEEDBACK_WEBHOOK_URL`，
  支持 `generic` / `feishu` / `wecom` 三种载荷格式，失败只记日志不影响反馈入库。
- **PC 端与 H5 端各增加一个反馈入口**：
  - 电脑端顶栏按钮 + `Ctrl+Shift+F` 快捷键，弹窗内可上传截图并一键附带诊断信息；
  - H5 端首页悬浮按钮与设置页入口。
- **客户端诊断采集**：捕获页面未捕获异常、Promise 未处理拒绝、控制台报错与失败请求，
  连同当前路由、视口、主题、网络状态一起提交；只在内存保留最近若干条，刷新即清空。
- 新增配置项：`FEEDBACK_TEST_CODE`（内部测试口令）、`FEEDBACK_WEBHOOK_URL`、
  `FEEDBACK_WEBHOOK_KIND`、`FEEDBACK_WEBHOOK_SECRET`、`FEEDBACK_ADMIN_BASE_URL`、
  `FEEDBACK_PRIVATE_DIR`。

## Impact

- **后端**：新增 `feedbacks` 表与迁移；新增 `feedback` 路由；新增 `feedback_storage`
  与 `feedback_notify` 两个服务；`config.py` 与 `.env.example` 新增配置项。
- **前端**：`desktop-frontend/` 新增诊断采集器、反馈 API、反馈弹窗与顶栏入口；
  `frontend/` 新增诊断采集器、反馈 API、反馈页面与两处入口；
  `admin-frontend/` 新增反馈箱页面、路由与菜单项。
- **契约**：`release/openapi.json` 与 `frontend/src/types/generated-api.ts` 需随接口重新生成。
- **风险与约束**：
  - 反馈内容可能包含第三方信息，截图因此不公开、不进公开媒体目录，管理台以外无法读取；
  - 免登录提交依赖共享口令，口令为空时该路径整体关闭（生产环境默认关闭）；
  - 反馈为内部测试用途，不做公开可见的评论或帖子联动；
  - 真实姓名与学号不出现在任何反馈响应里，只保留账号引用。
