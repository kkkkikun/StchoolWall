# SNAPSHOT — SchoolWall 项目状态快照

> 最后更新：2026-07-06 ｜ 分支：main ｜ 维护者：开发团队（assistant 按需更新）
> 用途：新会话进入项目时的第一份"现在在哪"快照。规则全文见 `openspec/specs/`，本文件只记状态。

---

## 项目一句话

SchoolWall（鄂应墙）—— 校园匿名墙 / 信息撮合平台，微信小程序 + FastAPI，核心是"微信静默授权 + 正方教务系统学籍实名"双 JWT 体系。

---

## 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 后端框架 | FastAPI + Uvicorn（全异步） | 0.115.6 / 0.34.0 |
| 语言 | Python | 3.10（实测 3.10.12） |
| ORM / DB | SQLAlchemy 2.0 async + asyncpg + Alembic | 2.0.36 / 0.30.0 / 1.14.0 |
| 数据库 | PostgreSQL | 15-alpine |
| 缓存/队列 | Redis（hiredis） | 7-alpine / 5.2.1 |
| 认证 | python-jose JWT + 正方爬虫（rsa + bs4 + httpx） | 3.3.0 |
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
│   │   ├── api/               # admin / auth / posts / tags
│   │   ├── components/
│   │   ├── pages/             # admin / index / mine / my-posts / post-detail / publish / tags / verify
│   │   ├── types/
│   │   ├── utils/             # request / storage
│   │   ├── App.vue / main.ts / pages.json / manifest.json
│   ├── package.json
│   └── vite.config.ts
├── openspec/                  # 规范体系（本初始化产物）
│   ├── config.yaml
│   ├── specs/                 # architecture / rules / learned / references / optimization
│   └── changes/               # 变更提案（当前无）
├── .claude/
│   ├── docs/                  # SNAPSHOT.md / tasks.md（本目录）
│   ├── skills/                # openspec-*-change / explore / propose / sync-specs
│   └── commands/opsx/         # /opsx:propose|explore|apply|archive|sync
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

## 当前工作 / 下一步

- 前端多页面体系正在搭建中（发帖/详情/我的发布/标签/管理/认证），尚未提交 —— 详见 `.claude/docs/tasks.md`。
- OpenSpec 规范体系刚初始化完成（5 个 spec 全部校验通过）。
