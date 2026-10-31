# SNAPSHOT — SchoolWall 项目状态快照

> 最后更新：2026-10-31 ｜ 分支：main（已合入主线，合并点 d7fe503，来源分支 feature/main-quality-port） ｜ 维护者：开发团队（assistant 按需更新）
> 用途：新会话进入项目时的第一份"现在在哪"快照。规则全文见 `openspec/specs/`，本文件只记状态。

---

## 项目一句话

SchoolWall（鄂应墙）—— 单校校园社区，Web→微信小程序→Android，固定昵称。统一身份/短会话，学生证私有材料人工核验；教务密码认证停用。PostgreSQL持久审核任务、腾讯云机器辅助与人工队列、独立MFA管理台、发布和恢复门禁。2026-10-16用户批准生产化改造，现仍在验收中，未真实发布。

当前代码/测试/阻断见 docs/production/implementation-status.md、verification.md；活跃OpenSpec：production-multiplatform。下方历史栈与进度作为旧版本背景，依赖准确版本以锁文件为准。

2026-10-30 进展：主前端npm audit高危清零（0 high/0 critical；管理台0 vulnerabilities）；新增浏览器级全量走查（学生端26页面×亮/暗53/53，管理台17路由×桌面/窄屏34/34，含横向溢出与WCAG对比度断言）；修复夜间模式文字色、输入占位符对比度、管理台Element Plus语义色，以及图片展示顺序缺陷（新增 media_assets.position 列，迁移 b7e2c4a91d30）。新增迁移与媒体顺序后端用例尚未在真实PostgreSQL执行。

2026-10-31 进展（主线平台化）：自 main 拉出 `feature/main-quality-port`，把主题分支的**非 UI 实现质量**整体移植回主线 —— 后端生产化（31 新文件 + 模型/路由/服务/配置改造 + 迁移 529bf8becb3f、b7e2c4a91d30）、依赖高危清零、浏览器级走查体系与两个永久审计脚本、本地预览服务（含管理台登录 mock）、学生端统一图标体系（188 SVG / 97 语义名，emoji 清零）、语义化设计令牌、白天/夜晚双模式主题机制、管理台补齐三视图。**配色沿用 main 自己的玫瑰红品牌**（`--primary: #c2455c`，白字 4.88:1），未引入 X 蓝。移植中修复既有缺陷：底栏图标指向已删目录导致 5 个图标全部 404 不显示、走查断言写死色值、静态守卫按品牌色名判定失效、webview 引用不存在图标、本地 .env 与短会话契约冲突；另补齐漏带的 5 个前端回归测试与 1 个管理台测试（前端 12→55 项）。收尾复审再修：暗色底栏激活标签 3.88:1 改用 `--primary-text`（品牌例外 6→0）、18 个走查脚本静态服务改多线程（消除偶发 ERR_CONNECTION_CLOSED）、管理台 Element Plus 默认占位符 2.30:1 覆写为 5.27:1、清除 3 处 X 蓝残留。复验：客观扫描 25 页 × 亮/暗 全部缺陷归零且品牌例外归零；全页面走查 57/57、桌面平板 16/16、发布 6/6、图片上传 10/10、登录守卫 11/11、详情互动 33/33、管理台全视图 34/34 + 管理台自身 ui-walkthrough 8/8 全 PASS；前端单测 55/55、管理台 12/12；三端构建通过。**未执行**：后端 pytest 与迁移 upgrade/downgrade（无 PostgreSQL/Redis/Docker）、微信开发者工具与真机实测。
2026-10-31 已合并入 main（合并点 d7fe503，`--no-ff` 保留分支轨迹）。合并后 main 上复验：type-check 双端 0 错、前端单测 55/55、管理台 12/12、三端构建通过、`app.main` 导入成功、运维脚本 20 passed、openspec 7/7。分支 `feature/main-quality-port` 保留未删除，便于回退或对照。

2026-10-31 改进批次二（管理台体积优化）：Element Plus 改按需引入（`unplugin-vue-components` + `unplugin-auto-import`），**首屏 411KB → 102KB gzip（-75%）、raw 1458KB → 303KB（-79%），主 chunk 1099KB → 249KB，全部 CSS 353KB → 264KB**；locale 改用 `provideGlobalConfig({locale}, app)` 保住中文（MessageBox 按钮实测「取消/确定」）。配套修掉四处隐藏问题：① 按需注入的组件样式落在品牌主题之后、Element Plus 默认蓝反盖玫瑰红（走查 34/34 全挂、按钮对比度掉到 2.78:1）→ `theme.css` 选择器提到 `html:root` / `html.dark:root`；② 组件声明出真实类型后暴露 42 处被 `any` 掩盖的类型不匹配 → 模板标注 `row as X`、el-tag 映射表标注 `TagProps['type']`；③ 服务型 API 样式落进懒加载视图 chunk、主 chunk 的 `request.ts` 提示无样式 → 服务型样式改在 `main.ts` 引入；④ 管理台单测用 Node loader 直读源码、绕过自动注入（12/12 → 9/12）→ `request.ts` 保留显式 `ElMessage` 导入、样式留在 `main.ts`。`build` 脚本改为 `vite build && vue-tsc --noEmit` 以免 dts 与类型检查互相卡死，生成的 dts 提交入库。新增 `admin-frontend/scripts/style-coverage-check.py` 守护样式齐全（已负向验证并接入 CI）。npm audit 未新增告警。

2026-10-31 改进批次一（CI 守护 + 文档校准）：① **CI 覆盖补全** —— 此前只跑 `npm run test:auth`（1 脚本 10 项），现接入前端+管理台全量单测、`@fission-ai/openspec@1.4.1 validate --specs`、18 套浏览器走查、客观缺陷扫描（起 `scripts/preview.py` 供数）；两份 workflow 经 actionlint 1.7.7 通过。② **管理台走查与部署前缀对齐** —— CI 用 `--base=/admin/` 出制品（nginx 亦为 `location /admin/`），而走查静态服务把 dist 挂根路径，导致 34 场景全挂（资源 404 → SPA 回退返回 text/html → 模块脚本被拒）；抽出共享模块 `admin-frontend/scripts/walkthrough_server.py`（顺带消除 11 份重复的 SPAHandler），按 `ADMIN_BASE_PREFIX` 剥离前缀，11 套走查在 `--base=/admin/` 产物下全 PASS。③ **文档与实测对齐** —— `release-gates.md` G1 仍写「21 项 high」（实为 0 high/0 critical）、`client-release-validation.md` 写管理台「0 vulnerabilities」（实为 3 moderate）、前端「17 moderate」（实为 20）、残留「X 品牌蓝既定取舍」旧描述。④ `openspec/specs/optimization/spec.md` 从空模板补齐优化点清单，每条含当前影响/建议方案/验证方式。
---

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI + Uvicorn（全异步） | 0.115.6 / 0.34.0 |
| 语言 | Python | 3.10（实测 3.10.12） |
| ORM / DB | SQLAlchemy 2.0 async + asyncpg + Alembic | 2.0.36 / 0.30.0 / 1.14.0 |
| 数据库 | PostgreSQL | 15-alpine |
| 缓存/队列 | Redis（hiredis） | 7-alpine / 5.2.1 |
| 认证 | PyJWT + 正方爬虫（rsa + bs4 + httpx） | 2.10.1 |
| 存储 | boto3 适配器（local / R2 / aliyun） | 1.36.2 |
| 前端 | uni-app (Vue 3 + Vite 5 + TS 4.9) | dcloudio 3.0.0-408 |
| 基础设施 | Docker Compose；生产 Nginx + HTTPS | — |
| 测试 | pytest + pytest-asyncio | 8.3.4 / 0.24.0 |

---

## 项目结构树

```
SchoolWall/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口，路由注册，CORS
│   │   ├── config.py          # Settings（环境变量集中）
│   │   ├── database.py        # 异步引擎/session
│   │   ├── dependencies.py    # Depends: DB、当前用户、限流
│   │   ├── models/            # post / report / tag / user
│   │   ├── routers/           # admin / auth / posts / tags / upload / user
│   │   ├── schemas/           # Pydantic（对应各 router）
│   │   ├── services/          # admin / auth / moderation / post / tag
│   │   └── utils/             # moderation / rate_limit / redis / security / storage / zhengfang
│   ├── alembic/versions/      # 迁移脚本（61edfd32690b_init_tables）
│   ├── tests/                 # conftest + test_{auth,posts,...}.py（独立测试库）
│   ├── requirements.txt
│   ├── pytest.ini             # asyncio_mode=auto
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── api/               # auth / posts / notification / banner ...
│   │   ├── components/
│   │   ├── pages/             # index / group / publish / message / mine / post-detail / search / verify / settings ...
│   │   ├── static/ref/        # 自定义图标（search-copy.svg 等，ASCII 文件名）
│   │   ├── types/
│   │   ├── utils/             # request / storage
│   │   ├── App.vue / main.ts / pages.json / manifest.json
│   ├── package.json
│   └── vite.config.ts
├── admin-frontend/            # 独立 Web 管理后台（Vue3 + Element Plus + Pinia + ECharts）
│   └── src/
│       ├── views/             # Login / Dashboard / Posts / Users / Reports / Banners / Comments / Parties / Announcements / Logs
│       ├── api/               # auth / stats / posts / users / reports / banners / operations
│       ├── stores/            # Pinia auth
│       ├── layouts/ router/ utils/
│       └── vite.config.ts     # 端口 5174，代理 /api /static → :8000
├── openspec/                  # 规范体系（本初始化产物）
│   ├── config.yaml
│   ├── specs/                 # architecture / rules / learned / references / optimization
│   └── changes/               # 变更提案（当前无）
├── .claude/
│   ├── docs/                  # SNAPSHOT.md / tasks.md（本目录）
│   ├── skills/                # openspec-*-change / explore / propose / sync-specs
│   └── commands/opsx/         # /opsx:propose|explore|apply|archive|sync
├── deploy/                    # 生产部署产物（Dockerfile/compose.prod/nginx）+ ci/（CI 管线）
│   └── ci/                    # 全 Docker 化 CI：ci.sh 编排 + compose.ci 测试栈 + systemd timer 接入件
├── ref/                       # 前端设计参考稿（页面 md + svg 图标）
├── 原型导出/                   # 页面截图 PNG + 自包含 HTML（给设计工具导入）
├── SchoolWall.md              # MVP 技术实现文档（原始需求）
├── docker-compose.yml         # PostgreSQL + Redis
└── .env.example
```

---

## 关键文件速查

| 文件 | 作用 |
|------|------|
| `backend/app/main.py` | 路由前缀注册：`/api/v1/{auth,user,posts,upload,tags,admin}` + `/health` |
| `backend/app/config.py` | 所有环境变量（DB/Redis/JWT/微信/存储/正方） |
| `backend/app/utils/zhengfang.py` | 正方教务系统 RSA 登录 + 抓 real_name（密码不落库） |
| `backend/app/utils/storage.py` | local / R2 / aliyun 存储适配器 |
| `backend/app/services/moderation.py` | 异步内容审核后台任务 |
| `backend/tests/conftest.py` | 测试隔离：独立库 + NullPool + TRUNCATE |
| `frontend/src/utils/request.ts` | 前端请求封装（JWT 注入、错误码） |
| `SchoolWall.md` | 原始 MVP 设计文档 |

---

## Git 状态（2026-07-06）

- 分支：`main`
- 最近提交（自下而上）：
  1. `c3458df` feat: initialize project scaffold
  2. `ed8d685` feat(posts): implement post CRUD with privacy isolation and comprehensive tests
  3. `996055f` feat(upload): implement storage adapter with local and R2 support
  4. `e48ad3b` feat(tags,admin): add tag management and admin dashboard APIs
  5. `c464152` / `7947e89` feat(moderation): add async background task for post image moderation
- **未提交工作区**（前端为主）：
  - 已改：`pages.json`、`pages/index/index.vue`、`pages/mine/index.vue`、`pages/verify/index.vue`、`utils/request.ts`、`vite.config.ts`
  - 新增未跟踪：`frontend/src/api/`、`components/`、`pages/{admin,my-posts,post-detail,publish,tags}/`、`static/tabbar/`、`types/`、`utils/storage.ts`、`.env.example`
  - **解读**：前端正在从脚手架扩展为完整页面（发帖、详情、我的发布、标签、管理后台、认证页），尚未提交。
- **本次初始化新增**：`openspec/`、`.claude/docs/`、`CLAUDE.md`（未跟踪）

---

## 已完成能力（按提交推断）

- [x] 项目脚手架（FastAPI + uni-app + Docker Compose）
- [x] 帖子 CRUD + 隐私隔离（含测试）
- [x] 上传 + 存储适配器（local / R2）
- [x] 标签管理 + 管理后台 API
- [x] 异步内容审核后台任务（帖子图片）
- [x] 认证链路（微信 + 正方学籍绑定，含安全红线）
- [x] 限流（Redis）
- [x] 社交闭环：互动（评论/点赞/收藏/足迹）+ 发现（热帖/搜索/分类）+ 通知 + 组局 + 关注/个人主页
- [x] Banner 独立轮播表（投放窗口/上下架/排序；旧广告帖不再混 feed）
- [x] 管理员置顶（推荐位第一页前置置顶块，主流排除防重复）
- [x] 真实内容审核（微信 msg_sec_check v2 + img_sec_check；pass/reject/review/error 四分流，fail-open 降级，审核通知）
- [x] **自动审核本地规则层 + 可观测性**（2026-09-03，3 批次 TDD）：
  - 本地敏感词：归一化子串匹配（NFKC/小写/去空白零宽，防全角与插空格变体），hard→直接拒绝 / gray→转人工，与微信层并联取最严（本地已 reject 跳过微信省配额）
  - 频率风控：同用户 10 分钟 ≥3 帖 → 转人工（DB count，不依赖 Redis）
  - `sensitive_words` 表（管理后台 CRUD + 审计 sensitive_word.*，迁移内置 20 条种子词）
  - `moderation_records` 表：每次审核按来源（rule/wechat）落行（matched/reason/trace_id），review 分支补 commit 修复记录丢失
  - 管理端新增两页：敏感词库 🚫 / 审核记录 🛡️（GET /admin/sensitive-words CRUD + GET /admin/moderation-records）
  - 设计约束：本地判定先于微信重试循环算一次（review 严重度>error，折进循环会中断重试）；记录仅循环退出后写一次防重试重复
- [x] GET /posts/my（我的帖子，含待审/封禁状态筛选）
- [x] 设置页 + 退出登录（frontend/pages/settings）
- [x] **独立 Web 管理后台**（2026-08-31 完成，8 批次）：
  - 管理员账号密码体系：独立 `admin_users` 表（bcrypt rounds=12）+ Console JWT（scope=admin_console，12h，pwd_version 改密全端失效）+ CLI `python -m app.create_admin`
  - 双 token 兼容：`require_admin_console` 同时接受 console JWT 与旧 users.role=admin JWT
  - 审计日志：`admin_logs` 表全量留痕（操作者/动作/目标/detail/IP），写操作显式 `log_admin_action`
  - 帖子精细管理：多条件筛选 + 编辑 + 批量状态（≤100）+ 置顶
  - 用户精细管理：搜索/角色/认证/冻结筛选 + 改角色（防自降）+ 详情聚合
  - 评论软删（计数联动）、组局状态流转、公告群发（复用 notifications +payload/batch_id）、趋势统计（上海时区）、CSV 流式导出（UTF-8 BOM，用户导出强制审计）
  - `/static` 静态挂载 + 管理端图片上传（路径穿越防护）
  - admin-frontend 10 页（Vue3 + Element Plus + ECharts 看板）
  - 小程序内嵌管理页已下线（保留跳转提示页）

## 当前工作 / 下一步

- 2026-08-31：独立管理后台 8 批次全部完成，307 tests passed，双端 type-check 0 错。
- 2026-09-03：自动审核系统激活（本地规则层 + 审核记录，366 tests passed）；dev 库已可用——学生帖现在会真实经过敏感词/频率判定。9-03 早些时候完成：编辑资料页、个人主页"我的"风格重做、check-in/精华/热榜/消息页改版（均已提交 bec3ae..c438c20）。
- 2026-09-05：**发布页图片全流程**（openspec/changes/post-images）：添加照片真实可用——多选≤6张/压缩/服务端 uuid 落盘/网格预览删除重试/未完成阻止提交；隐藏视频假按钮。修复两个存量 bug：post-card 引用不存在的 default-avatar.png（EISDIR 隐患，改首字符色块兜底）、my-posts 头像昵称区因 author/user 字段不匹配从未渲染（组件内归一化）。E2E 实证带图发布闭环；后端 420 tests 零改动零影响。同日完成：网页登录（web:{username} 命名空间 + bcrypt + 双限流，420 tests）与部署产物（backend/Dockerfile、deploy/{compose.prod,nginx.conf,README}，容器/构建均验证）。
- 2026-09-11：**服务器端 CI 管线 + 微信小程序兼容准备**（openspec/changes/{server-ci,mp-weixin-compat}）：
  - `deploy/ci/`：全 Docker 化 CI（服务器只需 docker）——隔离测试栈 ci-db:5433/ci-redis:6380 仅绑本机、跑完 down -v；ci.sh 五阶段（起栈/后端镜像/pytest/前端 type-check+H5+MP 构建/admin 构建）→ report.html + mp-weixin 产物留档；run-ci.sh + systemd timer（hourly，origin/main 无新提交则跳过）+ install.sh 一键安装。本地 WSL 全量验证：425 passed + 3 skipped + 三构建绿，exit 0。
  - 小程序兼容：静态审计零 H5-only API 泄漏；build:mp-weixin 通过（19 页产物完整，touristappid + urlCheck:false）；`frontend/README-MP.md` devtools 手册。待用户：申请微信测试号配 WECHAT_APP_ID/SECRET 跑通登录链路、devtools 实测。
  - CI 环境要点：容器需传 ZHENGFANG_BASE_URL 非空值（/auth/verify 配置门禁，空则 4 个认证测试 400）；WSL 首跑需 mirror 预热 python:3.10-slim（docker.io 被墙）。
- 2026-09-04：**安全加固 5 批全部完成**（openspec/changes/security-hardening，412 tests passed）：JWT 密钥轮换+生产 fail-fast；ENVIRONMENT 默认 production + dev-login 双闸（.env 需 DEV_LOGIN_ENABLED=true）；上传 kind 白名单+服务端 uuid 路径（前端 uploadFile 同步改 kind）；封禁/待审帖详情与互动 status==1 门禁；images 限 /static/ 杀 SSRF；发帖/评论/举报/上传按用户限流+管理台按用户名退避；pyjwt 替换 python-jose；escape_like/CSV 公式注入/body 上限/join 行锁/wechat_id 收敛至交易帖型；compose 端口绑 127.0.0.1。遗留 backlog：7 天用户 token 无撤销、上传魔数嗅探、管理台 httpOnly cookie 化。
- 2026-09-28：**GitHub Actions SSH 自动部署上线**（`.github/workflows/deploy.yml` + `deploy/GH_ACTIONS.md`）：push main 触发 → SSH 到服务器 → git pull --ff-only → docker(node:20-alpine) 构建 H5+管理台 → rsync 到 /var/www/schoolwall/{h5,admin} → compose up -d --build（自动迁移）→ /health 轮询门禁；concurrency 防并发，支持 workflow_dispatch。Secrets：SERVER_HOST/USERNAME/SSH_KEY（+可选 DEPLOY_PATH/WEB_ROOT）。服务器侧开通踩坑（均已解决）：① sshd 默认 `PubkeyAuthentication no`（加 drop-in 99-pubkey-auth.conf 修复）；② get.docker.com 脚本因 focal 源缺 docker-model-plugin 中断、download.docker.com TLS 被墙 → 改用 Ubuntu 源 docker.io + GitHub 下 compose v2 插件；③ Docker Hub 被墙 → daemon.json 配 registry-mirrors（daocloud 等）。私有仓库 pull 凭证：服务器 Deploy key `schoolwall_git`（只读，gh api 添加，id 164676356）。首次部署全绿 `deploy ok: backend healthy`（5m19s）。
- 待办：真机 mp-weixin 联调（需配 WECHAT_APP_ID/SECRET 后微信审核层才真实生效，本地规则层已独立生效）；生产域名 HTTPS/nginx 待接入（workflow 不改 nginx，需按 deploy/README.md 手工一次）。
- 已知技术债：游标分页排序键已统一为 id DESC（修复 created_at/id 交叉导致的翻页重复）；admin 列表路由含 Report/User 的 created_at 排序仍有同样隐患（量小暂未修）。`frontend/src/static/default-avatar.png` 是目录不是文件（post-card 引用会触发 dev server EISDIR 崩溃，待修）。
- 本地开发环境：backend :8000（uvicorn --reload）、frontend H5 :5173（/tmp/schoolwall-h5.sh 自愈包装）、admin-frontend :5174；测试管理员账号 boss（2026-08-31 建）。
