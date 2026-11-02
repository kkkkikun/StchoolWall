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


