# Tasks — 内部测试反馈通道

## 批1：数据模型与私有存储

- [x] 新增 `backend/app/models/feedback.py`（类型、严重程度、页面环境、诊断 JSON、截图清单、状态流转）
- [x] 新增 Alembic 迁移 `d4e6f8a1b357_add_feedbacks.py`，挂在 head `b7e2c4a91d30` 之后
- [x] 新增 `backend/app/services/feedback_storage.py`：私有目录 `private-feedback/`、
      路径白名单、单张 ≤5MB、复用媒体归一化抹掉 EXIF
- [x] `backend/app/models/__init__.py` 注册新模型

## 批2：接口与推送

- [x] 新增 `backend/app/routers/feedback.py`：
      提交（登录或内部口令）、截图上传（上传令牌）、我的反馈、管理端列表/统计/详情/截图/状态流转
- [x] 新增 `backend/app/services/feedback_notify.py`：generic / feishu / wecom 三种载荷，失败只记日志
- [x] `backend/app/main.py` 注册 `/api/v1/feedback` 与 `/api/v1/admin/feedback`
- [x] `backend/app/config.py` 与 `.env.example` 新增 6 个 `FEEDBACK_*` 配置项
- [x] `backend/app/utils/rate_limit.py` 新增反馈限流（登录 20 次/小时，免登录 5 次/小时按 IP）
- [x] 重新导出 `release/openapi.json` 并重新生成 `frontend/src/types/generated-api.ts`

## 批3：电脑端

- [x] 新增 `desktop-frontend/src/utils/diagnostics.ts`：页面报错、未处理拒绝、控制台报错、
      失败请求、路由、视口、主题、网络状态；环形缓冲且刷新即清空
- [x] `desktop-frontend/src/utils/http.ts` 在响应拦截器里登记失败请求
- [x] 新增 `desktop-frontend/src/api/feedback.ts`：创建反馈、上传截图、我的反馈
- [x] 新增 `desktop-frontend/src/components/FeedbackDialog.vue`：类型、严重程度、标题、描述、
      截图上传、诊断开关、免登录口令与昵称
- [x] `desktop-frontend/src/layouts/DesktopLayout.vue` 顶栏加反馈入口与 `Ctrl+Shift+F` 快捷键；
      反馈弹窗懒加载，不占首屏体积
- [x] `desktop-frontend/tests/feedback-diagnostics.test.mjs` 覆盖采集、上限与清空

## 批4：H5 端与管理台

- [x] H5 端：`frontend/src/utils/diagnostics.ts` 诊断采集（异常、失败请求、路由、视口、主题、
      网络、平台，环形缓冲上限 50/20，客户端先裁到 24KB 避免撞后端 32KB 上限）
- [x] H5 端：`frontend/src/api/feedback.ts`（创建反馈、逐张上传截图、我的反馈）
- [x] H5 端：`frontend/src/pages/feedback/index.vue` 反馈页（类型、严重程度、标题与描述计数、
      截图 ≤5 张可删、诊断开关、免登录口令与昵称、提交回执与「查看我的反馈」）
- [x] H5 端：首页悬浮按钮（58×59px，SVG 图标）与设置页「意见反馈」入口；`pages.json` 注册且不进 tabBar
- [x] H5 端：`frontend/src/static/icons/common/feedback{,-primary,-inverse}.svg` 由 `gen_icons.py` 产出（无 emoji）
- [x] H5 端：`frontend/tests/diagnostics.test.mjs` 6 例单测
- [x] 管理台：`admin-frontend/src/api/feedback.ts`（列表/统计/详情/截图 Blob/更新 multipart）
- [x] 管理台：`admin-frontend/src/views/FeedbackView.vue` 反馈箱（状态概览、筛选、表格、详情抽屉、
      诊断日志代码块、截图预览、状态流转与备注）
- [x] 管理台：路由 `/feedback` 与侧边菜单「反馈箱」（复用 Element Plus SVG 图标）
- [x] 管理台：`admin-frontend/tests/feedback.test.mjs` 4 例单测

## 批5：验证与上线

- [x] `desktop-frontend`：`npm run type-check` 无报错、`npm test` 23 项全绿、`npm run build:desktop` 通过
      （主 chunk 370KB raw / 135KB gzip，反馈弹窗独立 chunk 37.8KB / 13.4KB gzip 不占首屏）
- [x] `frontend`：`npm run type-check` 无报错、`npm test` 61 项全绿、`npm run build:h5` 通过
- [x] `admin-frontend`：`npm run type-check` 无报错、`npm test` 16 项全绿、`npm run build:admin` 通过
- [x] `backend/tests/test_feedback.py`：15 项全绿（登录/免登录提交、口令校验、截图上传与越权、
      管理端列表与状态流转、三种 Webhook 载荷）—— 在服务器独立测试库上实跑取得
- [x] `node frontend/scripts/api-contract-check.mjs` 退出码 0（132 条路径，194 处字面量）
- [x] `npx @fission-ai/openspec@1.4.1 validate --specs` 7/7 通过；`validate feedback-channel` 通过
- [x] 修掉两个仓库级缺陷：① 前端与管理台的 `test` 脚本硬编码测试文件列表，
      新增测试不会被 CI 执行 → 改为 `tests/*.test.mjs` 通配；
      ② 管理台清空备注后保存会保留旧备注 → 后端区分「没传」与「传空」
- [ ] 后端全量 pytest 回归（CI 与服务器实跑各一次）
- [ ] 线上验收：电脑端与 H5 端提交反馈、截图入库、管理台查看、Webhook 推送
- [ ] 服务器 `.env` 配置 `FEEDBACK_TEST_CODE`（口令存 `~/.dsh/secrets/schoolwall-server.env`），
      `FEEDBACK_WEBHOOK_URL` 由负责人填入群机器人地址
