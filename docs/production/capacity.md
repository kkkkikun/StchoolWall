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
| PG 关键配置 | `shared_buffers=1GB`、`effective_cache_size=3GB`、`work_mem=16MB`、`maintenance_work_mem=256MB`、`max_connections=100`、`log_min_duration_statement=500ms`、`log_lock_waits=on`、`track_io_timing=on`、`jit=on`、`synchronous_commit=on` |
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

