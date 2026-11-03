# 容量基线与压测

当前没有可证明的RPS/并发承诺。此目录交付可重复的工具与验收目标，真实硬件、数据库、COS/审核配额和网络会影响结果。禁止直接对生产域名或真实学生数据运行容量种子/压力测试。

## 隔离准备

建立专用数据库schoolwall_loadtest与专用Redis逻辑库/实例。不得复用开发数据库、测试fixture库或生产Redis。应用ENVIRONMENT=test仅用于隔离压测环境，禁止公网部署此配置。使用真实Alembic升级建表，启动API和worker；接第三方时使用专用测试账号及明确预算，默认使用可控stub观察处理能力，不把stub吞吐当供应商吞吐。

```bash
cd backend
export ENVIRONMENT=test
export DATABASE_URL='postgresql+asyncpg://LOAD_USER:LOAD_PASSWORD@127.0.0.1:5432/schoolwall_loadtest'
export REDIS_URL='redis://127.0.0.1:6379/13'
export JWT_SECRET='load-environment-only-independent-random-secret'
export JWT_EXPIRE_MINUTES=15
python -m alembic upgrade head
ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE python ../scripts/load/seed.py --users 10000 --posts 100000 --comments 500000
```

种子三重限制test环境、*_loadtest库名、显式ACK，且拒绝已有帖子数据库。上面的正式验收命令生成1万个合成账号、10万帖子和50万评论（90天分布、5%帖子待审）；普通工具验证应显式降为10用户/100帖/少量评论，本地accounts.json权限0600。该文件包含测试JWT，禁止上传CI制品、日志和代码仓库。脚本默认较小规模1000用户/1万帖/5万评论，不替代正式数据基线；按首年容量估计递增，普通验证不能默认创建百万条。测试token仅由这个隔离种子生成，有效9小时、session 10小时，以覆盖8小时soak；生产token仍最多15分钟。9小时后重建隔离数据/凭证，禁止把测试token用于生产。

## 场景与接受条件

k6需要运营者安装并固定版本；脚本无对外通知。BASE_URL必须匹配ALLOWED_LOAD_HOST，且显式ACK。默认steady为100req/s持续30分钟，burst为200req/s持续5分钟，soak为100req/s持续8小时。每次迭代恰好发送一个业务请求，RATE为目标请求/秒；仍须记录实际HTTP RPS与dropped iterations，不能把发压速率当作成功吞吐。DURATION只用于明确标记的工具烟测，正式报告必须使用上述时长。

```bash
ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION ALLOWED_LOAD_HOST=127.0.0.1 BASE_URL=http://127.0.0.1:8000 PROFILE=steady RATE=100 k6 run scripts/load/campus.js
# 分别以 PROFILE=burst 和 PROFILE=soak 重复，输出保存在隔离运行目录。
```

45%最新流、25%详情、10%热榜、7%搜索、6%赞/取消、4%评论、3%未读，详情80%集中单热点。默认阈值为读p95≤500ms、写p95≤800ms、5xx<0.1%、无dropped iterations，另检查业务成功率>99%。429独立累计expected_rate_rejections，禁止将限流响应视为成功业务吞吐，需单独检查合理用户是否被校园NAT误伤。

补充真实认证→会话刷新、上传→隔离→审核→发帖、组局最后名额竞争、同一用户重复请求、发布期间流量、停worker重启、DB/Redis/审核超时和断网恢复场景；供应商调用速率须受预算限制，不用大规模压测消耗真实审核额度。验证重复消费无重复通知、计数一致、名额不超售、待审媒体不可公开。

## 报告与优化

报告包含commit/镜像digest、CPU内存磁盘/PG配置、数据量/分布、用户数、API与worker数、RPS/并发、p50/p95/p99、5xx/429、DB连接/锁等待/慢SQL、任务最旧年龄/死信、内存曲线和恢复耗时。目标是100req/s 30分钟、200req/s 5分钟和8小时长稳均通过、无持续资源增长、故障后任务可恢复；未实测保持G3未通过。

先针对慢SQL执行EXPLAIN (ANALYZE, BUFFERS)，比较新旧方案；优先组合/部分索引、稳定游标、热门公共内容缓存、异步浏览聚合、榜单预计算和对象存储/CDN。缓存不能混入个人点赞状态、会话或联系信息。负载增加前核算数据库连接总预算，禁止直接加连接或拆微服务。记录单位千次请求/GB存储/审核调用成本，预计月成本超预算80%告警，扩容要有实测收益。

## 2026-11-02 隔离环境实测（G3 数值取证）

本节记录一次真实执行的容量取证。**执行尚未全部完成，G3 仍为未通过**，结论见本节末尾与[验证记录](verification.md)。

### 隔离边界与防误伤

| 项 | 实际取值 |
|---|---|
| 应用运行环境 | `ENVIRONMENT=test`，仅监听 `127.0.0.1:8000`，未部署公网、未接触生产域名 |
| 数据库 | 专用隔离库 `schoolwall_loadtest` @ `127.0.0.1:55433`（本机独立 PostgreSQL 实例，与开发库/测试库/生产库互不相干） |
| Redis | 专用实例 `127.0.0.1:6399` 的逻辑库 **13**（未复用任何开发或生产 Redis） |
| 数据 | `scripts/load/seed.py` 生成的纯合成数据：10000 用户 / 100000 帖（95000 可见 + 5000 待审）/ 500000 评论；无真实学生数据、无真实昵称学号证件 |
| 种子守卫 | 未放宽：`ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE` + `ENVIRONMENT=test` + `*_loadtest` 库名三重限制，以及「拒绝已有帖子的数据库」保护原样生效（正式取证前先 `DROP DATABASE` 重建库再播种） |
| 凭证处置 | `accounts.json`（含 9 小时测试 token）写在隔离运行目录，权限 0600，**未入库、未进 CI 制品、未写日志**；报告只记录数量与签发方式，不记录 token 原文 |
| 发压守卫 | `ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION` + `ALLOWED_LOAD_HOST=127.0.0.1` + `BASE_URL` 必须匹配该 host；对生产域名发压会被脚本直接拒绝 |

### 执行环境

| 项 | 值 |
|---|---|
| 代码版本 | commit `9945322ddb2b994ac42fd9e990c1ea4e7c78193f`（main，PR #15 合并后的提交） |
| 镜像 digest | **无**：本机无 Docker，未构建也未推送镜像，实测为源码直跑 |
| 主机 | WSL2 / Ubuntu 22.04.5，AMD Ryzen 7 8845H（8 核 16 线程），内存 11.6 GB，根盘 1007 GB |
| 数据库 | PostgreSQL 15.19（apt.postgresql.org jammy-pgdg 二进制，本地非 root 实例，端口 55433） |
| 缓存 | Redis 7.2.5（源码编译，端口 6399，逻辑库 13） |
| 压测工具 | k6 v2.3.0（GitHub 官方 release 二进制） |
| 应用运行时 | Python 3.10.12 + `backend/requirements.txt` 锁定依赖（fastapi 0.143.2 / starlette 1.7.0 / uvicorn 0.34.0 / sqlalchemy 2.0.36 / asyncpg 0.30.0 / redis 5.2.1）；**Pillow 用 12.3.0 代替锁定的 13.0.0**，因为 Pillow 13.0.0 要求 Python ≥ 3.11 而本机只有 3.10.12（CI/生产为 Python 3.11.17） |
| PG 关键配置 | `shared_buffers=512MB`、`effective_cache_size=2GB`、`work_mem=16MB`、`maintenance_work_mem=256MB`、`max_connections=100`、`log_min_duration_statement=500ms`、`log_lock_waits=on`、`track_io_timing=on`、`jit=on`、`synchronous_commit=on` |
| API / worker | uvicorn **4 个 worker 进程**（127.0.0.1:8000）+ 后台 worker **1 个进程**；连接池 `DB_POOL_SIZE=10`、`DB_MAX_OVERFLOW=5`，连接预算 4×15+15=75 < `max_connections=100` |
| 负载发生位置 | k6 与 API/PG/Redis **同机**（同一台笔记本），存在资源竞争，记录时如实标注 |

> 该主机是共享的开发笔记本（内存 11.6 GB 且 swap 已占满、另有无关进程共跑），不是专用压测服务器；下文数值只能作为**同机基线**，不能当作生产容量承诺。

### 执行步骤（可复现）

```bash
# 1) 隔离实例与库
python -m venv /home/kikun/loadenv/pinned-venv && /home/kikun/loadenv/pinned-venv/bin/pip install -r backend/requirements.txt   # Pillow 除外，见上表
initdb -D <隔离数据目录> -U loaduser --auth=trust --encoding=UTF8 --locale=C.UTF-8
pg_ctl -D <隔离数据目录> -l <隔离日志> -w start     # 端口 55433，unix_socket_directories 指向可写目录
psql -d postgres -c 'CREATE DATABASE schoolwall_loadtest OWNER loaduser;'
redis-server --port 6399 --dir <隔离目录> --save '' --appendonly no   # 源码编译的 7.2.5

# 2) 迁移与播种（隔离库，真实 Alembic 升级链）
cd backend && python -m alembic upgrade head
ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE python ../scripts/load/seed.py \
  --users 10000 --posts 100000 --comments 500000 --output <隔离目录>/accounts.json

# 3) 启动 API 与 worker
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
python -m app.worker

# 4) 三个场景（k6 脚本与参数取自本文件上方）
ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION ALLOWED_LOAD_HOST=127.0.0.1 BASE_URL=http://127.0.0.1:8000 \
  PROFILE=steady RATE=100 DURATION=30m k6 run scripts/load/campus.js
# PROFILE=burst RATE=200 DURATION=5m；PROFILE=soak RATE=100 DURATION=8h
```

### 宿主限制：WSL2 虚拟机会被冻结（影响计时口径）

本次运行的宿主是 **WSL2** 虚拟机。压测过程中虚拟机曾被整体冻结 **70.2 分钟**（资源采样时间轴出现 `04:01:55Z → 05:12:10Z` 的空档，同期 k6 的墙钟显示 `1h30m` 而场景计时只走了 `20m22s/30m0s`）。冻结期间负载**没有**施加：

- k6 的场景计时随虚拟机停摆，因此**每个场景的有效负载时长**（steady 30 分钟、burst 5 分钟、soak 8 小时）仍然成立；
- 但**墙钟时间被消耗**：9 小时有效期的测试 token 会因冻结而提前到期，属于必须记录的 runner 限制；
- 冻结瞬间在途请求被打断，会产生个别 503 与被冻结的极端耗时（本次 steady 出现 47 个 503、最大单请求耗时 4211 秒），会污染 p99/max 与 dropped iterations。

因此本节所有数值都注明了是否跨越冻结窗口；跨窗的数据单独标注，不与干净数据混算。

### 瓶颈定位：热点帖单行写锁队列

PostgreSQL 日志把「尾部变慢」定位到了语句级：

- `log_min_duration_statement=500ms` 记录到的慢语句中，占绝大多数的是
  `UPDATE posts SET view_count=(posts.view_count + $1::INTEGER), updated_at=now() WHERE posts.id = $2::BIGINT`
  —— 即**帖子详情页的浏览数自增**（`backend/app/services/post.py:208`）；
- `log_lock_waits=on` 记录到同一行（relation 16997，tuple `(150,43)`）上的行级锁等待，单次等待队列最长 **38 个进程**；
- 压测场景本身要求「详情 80% 集中单热点」，于是**每一次详情浏览都对同一行 posts 做一次 UPDATE**，点赞/取消点赞路径还会对同一行做 `SELECT ... FOR UPDATE`，写请求在单行上串行排队；
- 官方 steady 窗口内 `UPDATE view_count` 慢语句 2651 条，p50 612ms、p90 2065ms、最大 9404ms，其中 637 条超过 1 秒。

这是**产品级瓶颈**而不是压测脚本问题：浏览计数与点赞状态被放在同步事务里更新，热点帖的单行成为全局串行点。仓库本文档「报告与优化」一节已经把「异步浏览聚合」列为优先手段（见 `openspec/specs/optimization/spec.md`），本次实测为该结论提供了第一份可复现的证据。

### 实测结果

#### 场景一：steady（100 req/s × 30 分钟）

干净窗口（`05:34:48Z → 06:04:51Z`，全程无冻结、无内存耗尽）。k6 实际发出 **179984** 次请求，平均 **99.96 req/s**。

| 指标 | 实测 | 接受条件 | 判定 |
|---|---|---|---|
| 读 p50 / p95 / p99 | 29.37ms / **435.26ms** / 531.01ms | p95 ≤ 500ms | 通过 |
| 写 p50 / p95 / p99 | 43.01ms / **147.42ms** / 377.61ms | p95 ≤ 800ms | 通过 |
| 业务成功率（checks） | **100.00%**（179984/179984） | > 99% | 通过 |
| 5xx | **0.00%**（0 次） | < 0.1% | 通过 |
| HTTP 失败率 | 0.00% | < 1% | 通过 |
| 429（`expected_rate_rejections`） | **0 次** | 单列、不计成功吞吐 | 无触发 |
| dropped iterations | **16** | 0 | **未通过** |
| 并发（VU） | 均值 13，峰值 66（上限 200） | — | — |

路由分布与脚本配比一致（180000 次请求）：最新流 45%（81000）、详情 25%（45000）、热榜 10%（18000）、搜索 7%（12597）、赞/取消 6%（10794）、评论 4%（7196）、未读 3%（5397）。

作为对照，**跨越 70 分钟冻结窗口的那一轮 steady**（`03:46:36Z → 05:29:19Z`）读 p95 为 530.77ms、写 p95 512.59ms、dropped iterations 4966、5xx 47 次（0.03%）、最大单请求耗时 4211 秒 —— 同一份代码、同一份数据，仅宿主状态不同即产生数量级差异，因此该轮数据**不作为正式记账**，只用于说明 runner 限制的影响。

#### 场景二：burst（200 req/s × 5 分钟）

窗口 `05:29:34Z → 05:34:38Z`，无冻结。目标 200 req/s，实际发出 **50377** 次请求、**167.36 req/s**（差额由 dropped iterations 承担）。

| 指标 | 实测 | 接受条件 | 判定 |
|---|---|---|---|
| 读 p50 / p95 / p99 | 694.38ms / **2743.72ms** / 4338.91ms | p95 ≤ 500ms | **未通过** |
| 写 p50 / p95 / p99 | 1498.13ms / **4063.85ms** / 5888.37ms | p95 ≤ 800ms | **未通过** |
| 业务成功率（checks） | 99.996%（50375/50377） | > 99% | 通过 |
| 5xx | 0.00%（0 次） | < 0.1% | 通过 |
| 429（`expected_rate_rejections`） | 0 次 | 单列 | 无触发 |
| dropped iterations | **9624** | 0 | **未通过** |

速率翻倍后，热点帖单行的写锁队列成为硬瓶颈：到达率执行器无法维持 200 req/s，延迟与丢弃同时上升。该场景**未通过**，与「热点帖单行写锁队列」定位一致。

#### 场景三：soak（100 req/s × 8 小时）—— 中止，未达 8 小时

窗口 `06:08:54Z → 13:31:27Z`，目标 8 小时。该轮**在第 7 小时 22 分 30 秒（占 8 小时的 92%）被 SIGTERM 中止**，k6 自身记录为 `test run was aborted because k6 received a 'terminated' signal`。

中止原因与被测负载无关：承载该轮压测的宿主上，与压测进程同属一棵进程树的 dsh-superagent 服务被停止，服务端在退出时终止了自己的子进程树，把仍在运行的 k6 一并带走（`run_soak_only.sh` → `run_profile.sh` → `k6` 三层随父进程一并消失）。k6 在被终止前完成 **2,644,809** 次迭代、**0** 次被中断迭代，仅最后时刻有 **21** 个在途迭代被打断。

| 指标 | 实测 | 接受条件 | 判定 |
|---|---|---|---|
| 实际运行时长 | **7h22m30s**（8 小时的 92%） | ≥ 8 小时 | **未通过** |
| 有效速率 | **99.61 req/s**（2,644,823 次请求） | 100 req/s | 达标 |
| 全部请求 p50 / p95 / p99 | 32.82ms / **467.04ms** / 732.82ms（最大 13353.99ms） | 读 p95 ≤ 500ms / 写 p95 ≤ 800ms | 参考值 |
| 业务成功率（checks） | 98.16%（2,596,310 / 2,644,823） | > 99% | **未通过** |
| 5xx | **1,355** 次（HTTP 层失败率 0.05%） | < 0.1% | 通过 |
| 429（`expected_rate_rejections`） | **47,158** | 单列、不计成功吞吐 | 已单列 |
| dropped iterations | **10,187** | 0 | **未通过** |

上表时延为**全部请求混合统计**（summary export 未按读/写拆分），不能直接与「读 p95 ≤ 500ms / 写 p95 ≤ 800ms」的分档接受条件逐条比对，故只作参考值、不据此判定读或写是否达标。

**该轮不作为正式 8 小时长稳报告记账。** 本文件的验收口径写明「未实测保持 G3 未通过」「未达 8 小时的 soak 不得按正式报告记账」；本轮在 92% 处被中止，不满足 8 小时时长条件，因此：

- `docs/production/release-gates.md` 的 G3 行**不改写为已通过**，G3 保持未通过；
- 上表数值作为**部分实测参考**留档：说明该系统在 100 req/s 持续 7 小时以上时，全部请求时延仍在 p95 ≤ 500ms 量级，但「无 dropped iterations」与「8 小时时长」两项接受条件均未达成；
- 剩余差距：需在**无宿主冻结、无进程树干扰**的专用环境重跑满 8 小时，并在解决热点帖单行写锁瓶颈后重测 burst 与 soak。
- 后续：该轮的两项差距已在 2026-11-03 的专用隔离环境复测中补齐（见下一节）；本节保留为 2026-11-02 那轮的历史记录，其「G3 保持未通过」的结论以下一节为准。


## 2026-11-03 隔离环境复测（G3：热点帖单行写锁修复后）

本节记录消除热点帖单行写锁瓶颈后的复测。**burst 已通过；soak 已于 2026-11-03T13:56:35Z 跑满 8 小时并记账**；steady（100 req/s × 30 分钟）在同一构建上补跑，结论见本节末尾与[验证记录](verification.md)。

### 瓶颈修复做了什么

- 详情页浏览数不再同步写 `posts` 行：改写入 `post_view_counters` 聚合缓冲（`INSERT ... ON CONFLICT DO UPDATE` 原子自增），由后台 worker 每 10 秒逐帖一个小事务折叠回 `posts.view_count`；详情接口返回「已折叠值 + 待折叠增量」（同一条语句的一致快照）。
- 点赞/取消赞/评论/收藏去掉 `SELECT ... FOR UPDATE`；计数改为原子自增并 `RETURNING`，计数语句不再依赖 `posts.status`（帖子被隐藏时计数不漂移）。
- `post_view_counters` **刻意不加到 `posts.id` 的外键**：外键检查会对父行取 KEY SHARE 锁，与 `FOR UPDATE` 互斥，会把刚拆掉的串行点重新引回来（详见 `openspec/specs/learned/spec.md`）。

### 隔离边界与环境

| 项 | 实际取值 |
|---|---|
| 宿主 | KVM 虚拟机 / Ubuntu 24.04.5 LTS（6.8.0-147-generic x86_64），128 vCPU、295 GB 内存、根盘 991 GB（用量 109 GB）；**专用隔离环境，无宿主冻结、无进程树干扰**（k6 以 `setsid` 脱离会话进程组启动） |
| 代码版本 | commit `2757118`（分支 `agent/fix-post-row-lock-1e6521eb2722`） |
| 镜像 digest | `schoolwall-loadtest@sha256:0bd2b931870eac06094c139b0241fea417c6972384b24985300c95c69959ce67`（由 `backend/Dockerfile` 构建；基础镜像 `python:3.11-slim` 经镜像站拉取，pip 走镜像站 index，与 CI 同源 Dockerfile） |
| 数据库 | PostgreSQL 15.14（`postgres:15-alpine` 容器，端口 55433，专用库 `schoolwall_loadtest`） |
| 缓存 | Redis 7.4.7（`redis:7-alpine` 容器，端口 6399，逻辑库 13；未复用任何开发或生产 Redis） |
| 压测工具 | k6 v0.57.0（源码构建，Go 1.22.2）；脚本 `scripts/load/campus.js`，参数与本文上方一致 |
| 应用运行时 | Python 3.11（镜像内 3.11.x）+ `backend/requirements.txt` 锁定依赖；uvicorn **4 个 worker 进程**（127.0.0.1:8000）+ 后台 worker **1 个进程**；`DB_POOL_SIZE=10`、`DB_MAX_OVERFLOW=5`，连接预算 4×15+15=75 < `max_connections=100` |
| PG 关键配置 | `shared_buffers=512MB`、`effective_cache_size=2GB`、`work_mem=16MB`、`maintenance_work_mem=256MB`、`max_connections=100`、`log_min_duration_statement=500ms`、`log_lock_waits=on`、`track_io_timing=on`、`jit=on`、`synchronous_commit=on` |
| 数据 | `scripts/load/seed.py` 生成的纯合成数据：10000 用户 / 100000 帖（95000 可见 + 5000 待审）/ 500000 评论；**无真实学生数据、无真实昵称学号证件** |
| 种子守卫 | 未放宽：`ALLOW_SYNTHETIC_LOAD_SEED=YES_ISOLATED_DATABASE` + `ENVIRONMENT=test` + `*_loadtest` 库名三重限制，以及「拒绝已有帖子的数据库」保护原样生效（正式取证前先 `DROP DATABASE` 重建库再播种） |
| 凭证处置 | `accounts.json`（含 9 小时测试 token）只写在隔离运行目录，**未入库、未进 CI 制品、未写日志**；报告只记录数量与签发方式，不记录 token 原文 |
| 发压守卫 | `ALLOW_ISOLATED_LOAD=YES_NONPRODUCTION` + `ALLOWED_LOAD_HOST=127.0.0.1` + `BASE_URL` 必须匹配该 host |

### 场景一：burst（200 req/s × 5 分钟）—— 通过

窗口 `05:51:14Z → 05:56:14Z`（5 分钟整，无冻结、无宿主干扰）。k6 实际发出 **60001** 次请求、平均 **199.69 req/s**。

| 指标 | 实测 | 接受条件 | 判定 |
|---|---|---|---|
| 读 p50 / p95 / p99 | 9.79ms / **340.16ms** / 383.88ms（最大 483.08ms） | p95 ≤ 500ms | **通过** |
| 写 p50 / p95 / p99 | 9.16ms / **20.11ms** / 40.10ms（最大 213.84ms） | p95 ≤ 800ms | **通过** |
| 业务成功率（checks） | **100.00%**（60001/60001） | > 99% | 通过 |
| 5xx | **0.00%**（0 次） | < 0.1% | 通过 |
| HTTP 失败率 | 0.00% | < 1% | 通过 |
| 429（`expected_rate_rejections`） | **0 次** | 单列、不计成功吞吐 | 无触发 |
| dropped iterations | **0** | 0 | **通过** |
| 实际速率 | **199.69 req/s** | 200 req/s | 通过 |
| 并发（VU） | 均值 26，峰值 32（上限 100） | — | — |

与修复前同口径对比（2026-11-02 那轮 burst）：读 p95 **2743.72ms → 340.16ms**、写 p95 **4063.85ms → 20.11ms**、dropped iterations **9624 → 0**、实际速率 **167.36 → 199.69 req/s**。压测期间 PostgreSQL `log_lock_waits=on` 记录到的行锁等待 **0 次**，`log_min_duration_statement=500ms` 在压测窗口内 **0 条**慢语句（修复前同一根因下慢语句集中在 `UPDATE posts SET view_count=...`）。

### 场景二：soak（100 req/s × 8 小时）—— 通过（2026-11-03T13:56:35Z 跑满）

启动 `2026-11-03T05:56:35Z`，k6 以 `setsid` 脱离会话进程组运行（宿主不再冻结、进程树不牵连），结束 `2026-11-03T13:56:35Z` —— **8 小时 00 分 03 秒，满量结束**。种子签发的 9 小时测试 token 覆盖全程（session 10 小时），无 401、无重认证。k6 实际发出 **2,880,000** 次迭代（100/s × 28,800s 的满量），平均 **99.999 req/s**。

| 指标 | 实测 | 接受条件 | 判定 |
|---|---|---|---|
| 时长 / 迭代数 | 8h00m03s / **2,880,000** | 满 8 小时 | **通过** |
| 实际速率 | **99.999 req/s** | 100 req/s | 通过 |
| 读 p50 / p95 / p99 | 9.28ms / **345.78ms** / 402.07ms（最大 587.53ms） | p95 ≤ 500ms | **通过** |
| 写 p50 / p95 / p99 | 7.89ms / **15.54ms** / 22.11ms（最大 264.91ms） | p95 ≤ 800ms | **通过** |
| 业务成功率（429 单列后） | **100.00%**（2,830,914 / 2,830,914） | > 99% | **通过** |
| 429（`expected_rate_rejections`） | **49,086 次（1.70%）** | 单列、不计成功吞吐 | 已单列 |
| 5xx | **0.00%**（0 次） | < 0.1% | **通过** |
| HTTP 失败率 | 0.00% | < 1% | 通过 |
| dropped iterations | **0** | 0 | **通过** |
| 并发（VU） | 均值 16，峰值 24（上限 100） | — | — |

> **429 与成功吞吐的口径**：k6 脚本把 429 计入 `successful business response` 检查，所以脚本内建阈值 `checks: rate>0.99` 实测为 **98.30%** 并被跨越（`thresholds on metrics 'checks' have been crossed`）。本文档既定口径是「429 独立累计 `expected_rate_rejections`，禁止将限流响应视为成功业务吞吐」，故成功吞吐按 **2,830,914 / (2,880,000 − 49,086) = 100.00%** 记。两个数字都如实记录，不做取舍隐藏；49,086 次全部是 429（`expected_rate_rejections` 与检查失败数完全相等，且 `server_errors=0`、`http_req_failed=0`），没有混入其他非 2xx 响应。
>
> **429 的来源已定位**：全部来自「每用户 10 分钟 30 条评论」的限流（`backend/app/utils/rate_limit.py` 的 `RATE_COMMENT = (30, 600)`，键 `rl:u:<user_id>:comments`），不是应用异常、也不是 IP 层限流。压测脚本按 `sequence % 100` 固定请求类型、按 `sequence % 10000` 固定账号，少量账号因此反复发评论并触发限流：soak 窗口内的评论尝试为 4% × 2,880,000 = **115,200** 次，而数据库实际入库评论 **66,106** 条，差额 **49,094** 与 429 次数 **49,086** 基本一致（窗口边界差 8 条）。也就是说这 1.70% 的拒绝是限流按设计生效，**与「合理用户被校园 NAT 误伤」无关**（限流键是用户维度，不按 IP）。

#### 长稳期间的数据库证据

| 项 | 实测 |
|---|---|
| 行锁等待 | `log_lock_waits=on`，`05:56:35Z` 之后 **0 条** `still waiting for ...`；采样 CSV 的 `lock_not_granted` / `lock_wait_sessions` 全程 **0**（修复前同一 tuple 上曾排到 38 个进程） |
| 慢 SQL（>500ms） | 窗口内 **57 条**：53 条是帖子列表/详情共用的 `SELECT posts.*, users.* ...` 查询（PostgreSQL 日志按 `track_activity_query_size` 截断到 1024 字节，看不到 WHERE/ORDER BY 部分），最长 1475.9ms；另 4 条是取证用的全库计数核对 SQL（`SELECT count(*) FROM posts p WHERE p.like_count <> (...)`），属人工核对而非线上流量。**慢语句与行锁无关**（同窗口行锁等待 0 次），来源见下方执行计划 |
| 连接数 | 稳定 **35**（预算 4×15+15=75 < `max_connections=100`），活跃连接峰值 **11** |
| 任务最旧年龄 | pending 峰值 **4**，**最旧待审任务年龄峰值 1 秒** |
| 死信 | **0**（压测窗口内没有任何 `status='dead'` 的任务；采样 CSV 的 `jobs_failed` 列查的是 `status='failed'` —— 该状态在实现里并不存在，真正的死信口径是 `status='dead'`，两者在本轮均为 0）。soak 结束后即时核对：`jobs` 仅剩 `review=68,530`（人工复核终态），`pending`/`running`/`dead` 均为 0 |

#### 内存曲线与恢复耗时（无持续资源增长）

| 采样 | API RSS | worker 内存 | PostgreSQL 内存 | API CPU | 待折叠浏览量 |
|---|---|---|---|---|---|
| 第 1 小时均值 | 482.9 MB | 71.2 MiB | 0.384 GiB | 70.7% | 126 |
| 第 4 小时均值 | 483.0 MB | 72.8 MiB | 0.431 GiB | 71.6% | 77 |
| 第 8 小时均值 | 483.1 MB | 73.1 MiB | 0.481 GiB | 65.5% | 123 |
| 压测停止后 | 483.2 MB | 73.4 MiB | 0.482 GiB（平台期） | **0.7%** | 0 |

- API 进程 RSS 全程 **483 MB 几乎不变**（8 小时 +0.06%），worker 67.6→73.4MiB，PostgreSQL 0.374→0.482GiB（共享缓冲填充）后**进入平台期不再增长** —— 无持续资源增长。
- **恢复耗时**：压测于 `13:56:35Z` 结束后，**6 秒内**（首个采样 `13:56:41Z`）API CPU 由 73.7% 回落到 **0.7%**、连接数回到基线 35、待折叠浏览量归零；**无需重启进程，内存无回收需求**。

#### 计数 / 名额一致性

- 热点帖（id=100000）：`like_count` **298** = `likes` 行数 **298**；`comment_count` **1** = 公开评论 **1**；`view_count` **589,156** 且待折叠增量 **0**；足迹 2,500 行。
- **全库**：`like_count` 与 `likes` 表不一致的帖子 **0** 个；`comment_count` 与公开评论不一致的帖子 **0** 个。
- 组局名额：压测脚本未覆盖组局，单独场景见下节。

#### 任务恢复演练（故障后任务可恢复）

1. **租约过期恢复**：构造一条「worker 带着未过期租约崩溃」的任务（`status=running`、`lease_until` 已过期、attempts=1），运行中的 worker **≤2.1 秒**内重新领取并完成（attempts 1→2，终态 `review`）—— 崩溃残留的任务不会永久卡住。
2. **死信路径**：连续失败的任务按 `2^attempts` 退避重试（2s/4s/8s/16s），第 5 次失败后进入死信 `dead`（`last_error=ValueError`），从入队到死信约 **35 秒** —— 失败任务不会无限重试掩盖问题。两条演练任务的 `dedupe_key` 均以 `loadtest-` 开头，可与压测流量数据区分。

#### SQL 执行计划（`EXPLAIN (ANALYZE, BUFFERS)`，长稳后同一数据集，1 万用户 / 10 万帖 / 50 万评论）

| 语句 | 计划 | 耗时 |
|---|---|---|
| 热点帖详情（`posts` JOIN `users` 走主键，含 `visible_author` 反连接） | Nested Loop + 2 次 Index Scan（`posts_pkey` / `users_pkey`），反连接走 `user_blocks` 索引 | 0.258ms |
| 浏览计数合并（`posts` LEFT JOIN `post_view_counters`） | Nested Loop Left Join + `post_view_counters_pkey` Index Scan | 0.065ms |
| 最新流 feed（`order=time`，limit 21） | Index Scan Backward（`posts_pkey`）+ Memoize | 0.575ms |
| 热帖榜 `/api/v1/posts/hot`（近 7 天 + 加权排序） | Bitmap Index Scan（`ix_posts_created_at`，7 天内 7,238 行）→ Bitmap Heap Scan → Hash Join → top-N Sort | 15.733ms |
| 搜索 `/api/v1/posts/search?q=course`（`content ILIKE '%course%'`） | **Parallel Seq Scan（posts 31,667 行）** → Hash Join → Sort | **74.961ms** |
| 推荐流 `/api/v1/posts`（无 `order`，按热度分排序） | **Parallel Seq Scan（posts 31,667 行）** → Hash Join → Sort | **662.276ms** |
| 浏览计数写入（`ON CONFLICT` 原子自增） | Insert on `post_view_counters` → Conflict Resolution: UPDATE | 0.088ms |
| 点赞计数原子自增（`RETURNING`） | Update on `posts` → Index Scan `posts_pkey` | 0.385ms |
| 浏览计数折叠（worker 每 10 秒的 UPDATE） | Update on `posts` → Index Scan `posts_pkey` | 0.084ms |

对比修复前：慢语句集中在 `UPDATE posts SET view_count=...`（同一 tuple 串行），现在计数写入落在独立的 `post_view_counters` 行上、折叠每 10 秒一次、每次只锁一行且持锁毫秒级。

**剩余的长尾与行锁无关，来自帖子列表类查询的扫描面**：热帖榜靠 `ix_posts_created_at` 把候选集收窄到 7 天（15.7ms），但**搜索的 `ILIKE '%q%'` 与推荐流的热度分排序都要扫全表**（74.961ms / 662.276ms；热度分含 `now()`，无法用表达式索引直接排序）。k6 脚本只打 `order=time` 的最新流，因此推荐流这条最慢的路径不在本轮压测流量里，但它是学生端默认首屏（推荐位）。两条全表扫描已记入 `openspec/specs/optimization/spec.md` 作为下一条待办（搜索走 trigram/全文索引、推荐流走榜单预计算）。

### 场景三：steady（100 req/s × 30 分钟）—— 修复后补跑，通过

2026-11-02 那轮 steady 的 dropped iterations 为 16（未达标），且承载那一轮的宿主随后被冻结中止，按口径需在修复后的构建上补跑。本轮于 `2026-11-03T19:46:28Z` 在同一专用环境以同一脚本补跑（`setsid` 脱离会话进程组、目标 100 req/s × 30 分钟）；种子的 9 小时测试 token 已在 soak 结束后过期，补跑前按 `scripts/load/seed.py` 同一签发方式在隔离库内重新签发（新建 `user_sessions` + `create_access_token`，9 小时有效期），凭证只写隔离运行目录的私有文件。

| 指标 | 实测 | 接受条件 | 判定 |
|---|---|---|---|
| 实际速率 | **99.98 req/s**（180001 次迭代，30 分钟满量） | 100 req/s | 通过 |
| 读 p50 / p95 / p99 | 9.63ms / **354.72ms** / 403.42ms | p95 ≤ 500ms | **通过** |
| 写 p50 / p95 / p99 | 9.36ms / **16.31ms** / 23.40ms | p95 ≤ 800ms | **通过** |
| 业务成功率（429 单列后） | **100.00%** | > 99% | **通过** |
| 429（`expected_rate_rejections`） | **229 次** | 单列、不计成功吞吐 | 已单列 |
| 5xx | **0.00%**（0 次） | < 0.1% | **通过** |
| HTTP 失败率 | 0.00% | < 1% | 通过 |
| dropped iterations | **0** | 0 | **通过** |

与 2026-11-02 那轮 steady 相比：dropped iterations **16 → 0**（从「未达标」转为达标），读 p95 与写 p95 同步回落，且本轮全程无宿主冻结、无行锁等待。

### 场景四：组局最后名额竞争（名额一致性）

压测脚本未覆盖组局，用合成账号在隔离环境补跑「N 个用户并发抢最后几个名额」（组局由学生创建后先待审 `status=0`，隔离库里直接置为招募中 `status=1` 再开抢；抢名单位于 `parties` 行锁内的 check-then-increment，与帖子互动路径的去锁改造无关，此处刻意保留行锁）。

| 组局名额 | 并发报名人数 | 报名成功 | 「已满」拒绝 | `parties.joined_count` | `party_members` 行数 | 组局状态 | 判定 |
|---|---|---|---|---|---|---|---|
| 1 | 32 | **1** | 31 | **1** | **1** | 2（满额自动关闭） | 不超售 |
| 5 | 32 | **5** | 27 | **5** | **5** | 2（满额自动关闭） | 不超售 |

`join_party` 走 `SELECT ... FOR UPDATE` 串行化 check-then-increment（`backend/app/services/party.py`），并发抢名额时**恰好等于名额数的人报名成功、多一个都没有**，数据库计数与成员行数一致。

### 判定

- **burst：通过**（修复前未通过）。
- **soak：通过**（满 8 小时、延迟达标、5xx 0、dropped 0、无持续资源增长、锁等待 0 次、任务可恢复）。
- **steady：通过**（100 req/s × 30 分钟，dropped 0、延迟达标、业务成功率达标）。
- **组局名额竞争：通过**（32 抢 1 与 32 抢 5 均不超售）。
- **计数一致性与任务恢复报告：通过**（全库不一致帖数 0；租约过期 ≤2.1 秒被重新领取；连续失败 5 次进入死信）。
- **G3**：三个场景全部达标、必需证据齐备 —— `docs/production/release-gates.md` 的 G3 行据实更新为通过；同机基线不是生产容量承诺，生产等价拓扑与成本核算仍需人工安排。

