# 生产化交付与验收状态

更新：2026-10-16。用户批准的基线：单校、Web → 微信小程序 → Android、固定昵称、学生证人工核验、机器辅助审核、月基础设施预算500–1500元。

本文件记录代码交付与待验收项。代码、自动化检查、真实演练和平台准入分别记录，不以本地测试替代生产验收。

## 已实现的工程边界

- 用户UUID保持不变；登录身份、设备会话、学生证核验分表。密码与微信AppID作用域登录；显式短时配对，已有内容或认证的账号不自动合并。
- Access最长15分钟；refresh最长30天且轮换，只存SHA-256，保留轮换历史检测旧凭证重放。改密、找回、冻结、退出与注销撤销会话。Web HttpOnly刷新cookie+CSRF，Android Keystore适配，微信本地凭证适配。
- 最近登录可生成一次性找回码。找回码只显示一次，只存哈希；无找回码且丢失所有登录身份的账号需要人工支持流程，试运营前须公布支持渠道并完成演练。
- 独立管理台登录、生产强制TOTP、密钥加密保存、计数防重放；用户管理员JWT不再授权生产管理API。审核、证件访问和敏感导出留审计。
- 教务密码认证返回410。证件使用独立私有存储、随机拍摄码、独立HMAC指纹、版本化单独同意；结果7天/待审14天删除；认证到期降级。
- 图片真实解码、像素/尺寸限制、去EXIF、隔离存储、media_id所有权/用途验证；禁止任意路径读取和生产静态目录直出。
- PostgreSQL事务任务表、租约接管、有限重试、幂等、防过期机器决定覆盖人工状态。腾讯云文本/图片审核；配置缺失或故障不放行。管理台具备人工审核/故障重试入口。
- 内容与认证申诉记录，管理员复核并审计；接受申诉不自动发布内容。双向拉黑限制已登录发现与互动。公开内容不构成访问秘密，退出登录仍能浏览公共内容。
- 请求ID、统一安全错误、依赖故障503、健康/就绪检查、基本HTTP指标、任务队列指标（待处理数、最老待处理任务等待秒数、死信数、租约过期的运行中任务数，2026-11-04 起随应用 /metrics 暴露并接上告警规则）、DB/Redis 应用侧指标（连接池已用连接数、溢出连接数、连接预算、使用率比率与 Redis 调用失败计数，2026-11-04 起随应用 /metrics 暴露并接上告警规则；DB 锁等待与主机容量仍需对应 exporter，保持为缺口）、备份侧指标（最近一次成功备份距今的秒数、最近一次备份尝试是否成功、失败次数与状态是否读到了，2026-11-04 起随应用 /metrics 暴露并接上告警规则；信号来自仓库自控的逻辑备份 `deploy/backup.sh` 写下的状态文件，**WAL 归档/PITR、异机备份与备份加密仍需 pgBackRest 与人工安排，保持为缺口**）、连接与外部调用限制。
- CI、镜像扫描/依赖/密钥门禁、同一产物晋级、独立迁移、应用回滚、备份保留顺序修复、WAL/异机备份配置、压测脚本与发布证据门禁。

## 发布仍被阻断的事实

| 门禁 | 待完成证据 |
|---|---|
| G0 主体与平台 | 个人身份能否经营目标社区类目、域名/小程序/App备案、目标商店准入、实际主体/联系方式/隐私政策与SDK清单。配置中的example域名不能提交审核。 |
| G1 安全 | 依赖与镜像扫描零未豁免高危，独立安全复核，真实COS权限/版本清理检查，腾讯云额度/超时/费用验证；生产密钥及管理员TOTP配置。 |
| G2 可靠性 | 目标PostgreSQL15/Redis7全量CI（2026-11-02 已由 Production CI 通过：运行 41369377491，535 passed / 3 skipped，迁移链 upgrade/downgrade/再 upgrade PASS）、预发布进程杀死/重启、发布与回滚、真实异机备份恢复；RPO≤1h/RTO≤4h以实测为准。**2026-11-03 专用隔离环境已完成一次真实的备份→恢复→应用回滚演练**：逻辑备份 4.536 秒（43,929,696 字节，gzip --test 通过）、在新建隔离恢复库恢复 8.145 秒、38 张表逐表行数与内容 md5 一致（榜单刷新表与 RPO 标记表除外）、`scripts/check_restore.py` 在恢复库上 PASS、**RPO 实测 6.457 秒**（纯逻辑备份、无 WAL 归档口径）、`scripts/rollback-release.sh` 回滚 3.650 秒且回滚后 revision 切回上一版制品、schema 保留未降级；**仍未取得**异机备份、备份加密、WAL 归档/PITR 口径的 RPO、告警真实到达并被确认、以不可变 digest 制品的真实发布窗口，G2 仍为阻断，数值见 `docs/production/verification.md`。**2026-11-03 同一专用隔离环境完成故障注入演练**：杀 worker 后租约 **0.626 秒**被重新领取、连续失败 **5 次**进死信 `dead`（退避 **2/4/8/16 秒**）、审核供应商不可达时内容**保持待审不公开**且人工决定不被旧 worker 覆盖、Redis/DB 停容器后 `/health/ready` 返回 **503**、故障期间**半成品数据 0**、恢复 **3.88 / 4.45 秒**；**仍未取得**真实告警送达与人工确认、目标环境复测、真实腾讯云审核接口的额度/费用/SLA，另发现的「PostgreSQL 不可达时写路径返回 500 而非 503」代码缺陷**已于 2026-11-04 修复并复测**（写路径 **500 → 503**，body 为 `{"code":503,"message":"数据服务暂时不可用，请稍后重试"}`；故障期间 `/health/ready` 仍 503、`/health/live` 仍 200，恢复 **5.32 秒**，恢复后写入成功且无半成品数据；见 `docs/production/verification.md`）。**2026-11-04 同一专用隔离环境完成新增迁移 `b7e2c4a91d30` 的完整迁移链实测**：独立隔离库 `schoolwall_position_migration`（库名带 `_migration` 后缀、仓库自带 `scripts/check_migrations.py` 隔离守卫照旧生效）上 `upgrade head` → `downgrade 529bf8becb3f`（`media_assets.position` 列确已删除）→ `upgrade head` → `alembic check` 全部通过；媒体顺序后端用例 `backend/tests/test_production_pipeline.py` 20 passed，后端全量 pytest 575 passed / 3 skipped，API 契约 132 paths 不变（数值见 `docs/production/verification.md`）。 |
| G3 容量 | 2026-11-03 专用隔离环境（专用 KVM 虚拟机 + 容器化 PostgreSQL 15.14 / Redis 7.4.7，1 万用户/10 万帖/50 万评论**合成**数据，k6 v0.57.0）三个场景全部达标：steady（100req/s × 30 分钟）、burst（200req/s × 5 分钟，读 p95 340.16ms、写 p95 20.11ms、实际 199.69 req/s）、soak（100req/s × 8 小时跑满，2,880,000 次迭代、99.999 req/s、读 p95 345.78ms、写 p95 15.54ms、dropped iterations 0、5xx 0、429 49,086 次单列后成功吞吐 100.00%）；行锁等待 0 次、无持续资源增长、计数/名额一致性与任务恢复报告齐备，数值见 `docs/production/release-gates.md` 与 `docs/production/capacity.md`。**2026-11-03 补齐推荐流压测口径**（场景配比新增推荐流 `/api/v1/posts` 不带 `order`，有效占比 9.1%，既有场景权重不变）后按同一口径复测 burst：实际 199.893 req/s、读 p95 23.26ms、写 p95 18.37ms、dropped iterations 0、5xx 0、429 68 次单列、业务成功率 99.887%，推荐流路径实测 p95 18.19ms、其执行计划为索引扫描（Index Only Scan + 主键索引）单次 0.860ms。**仍需人工**：生产等价拓扑下的复测与每月成本核算（同机基线不是生产容量承诺）。 |
| G4 客户端 | 三端真实服务联调、浏览器跨标签refresh、微信隐私授权/真机分享、Android原生签名包/Keystore/拒绝及撤回隐私测试。 |
| G5 试运营 | 50→200→全校放量，审核积压、投诉、费用和故障处置验证，公布可实际响应的支持/申诉渠道。 |

主前端npm audit已于2026-10-30清零高危（0 high / 0 critical，管理台0 vulnerabilities）；残余moderate（2026-11-02 用官方 registry 重跑实测：全量 20 个告警包、生产口径 16 个）全部来自构建期依赖链 —— 17 个来自 `@intlify/core-base`，3 个来自 `openapi-typescript` → `@redocly/openapi-core` → `minimatch`，均为 devDependency 传递依赖，不进入客户端产物。原始报告见 `release/frontend-audit.json` 与 `release/frontend-audit-production.json`。镜像扫描与密钥扫描已于 2026-11-02 在 Production CI 实跑：密钥扫描（Gitleaks）通过，镜像扫描（Trivy）**失败** —— 基础镜像 `python:3.11-slim`（Debian 13.7）自带 46 条无修复版本 HIGH，另有镜像内 `setuptools` 内置依赖 2 条 HIGH，扫描失败即中止推送，未豁免高危；其中 `setuptools`/`wheel` 两条已由 2026-11-02 的 `backend/Dockerfile` 改动清理（安装层内移除运行期不需要的构建工具，`_vendor` 内置副本随之消失），**「python-pkg 层 0 HIGH」的权威证据已于 2026-11-03 由 main 分支 Production CI 运行 `41578409185` 给出**（Trivy `Report Summary` 里 65 个 `python-pkg` 目标逐条为 0，全表 `Total: 45 (HIGH: 45, CRITICAL: 0)` 全部来自 OS 层）；OS 层仍有 **45 条无修复版本 HIGH**（较 2026-11-02 少 1 条），需等 Debian 上游安全更新或走 `openspec/changes/` 提案换镜像族（人工决策）。独立安全复核仍未执行，G1门禁未解除。具体依赖链与处理条件见docs/client-release-validation.md，实际验证汇总见docs/production/verification.md。

生产发布脚本默认拒绝缺失证据或对应版本未获批准的发布；不得为了跑通脚本填写虚构证据。尚未部署或提交任何平台审核。

## 迁移与升级

迁移先备份并验证可读，再在预发布副本演练。保留原用户UUID，不以昵称/学号/UnionID自动合并。旧教务认证全部失效，删除旧姓名/学号并重新核验；演示身份停用；旧用户管理员权限降为游客。该隐私清理不可通过downgrade恢复数据。

旧公开图片路径不会自动获得审核通过，也不会通过生产静态目录直接公开。迁移前盘点存量图片并选择重新上传审核或人工审核导入；不得用开放旧/static方式临时绕过。

回滚恢复上一应用镜像，不自动逆向清理或回滚数据库。首个生产化迁移涉及旧认证清理，旧版本与新会话语义不兼容，首次切换需维护窗口及全员重新登录；后续迁移坚持扩展后收缩。

迁移链实测（2026-11-04，专用隔离环境：容器化 PostgreSQL 15.14 / Redis 7.4.7，独立隔离库 `schoolwall_position_migration`，库名带 `_migration` 后缀并走仓库自带 `scripts/check_migrations.py` 的隔离守卫）：对迁移 `b7e2c4a91d30`（`media_assets.position`，链上位于 `529bf8becb3f` → `b7e2c4a91d30` → `d4e6f8a1b357` → `c1d2e3f4a5b6` → `d7e8f9a0b123`）执行完整迁移链 —— `alembic upgrade head` → `alembic downgrade 529bf8becb3f`（`position` 列确已删除，列计数 0）→ `alembic upgrade head`（列恢复）→ `alembic check`（`No new upgrade operations detected.`），全部通过；`scripts/check_migrations.py` 守卫 PASS，媒体顺序后端用例 `backend/tests/test_production_pipeline.py` 20 passed（含 `test_bound_media_keeps_the_order_the_author_chose`），后端全量 pytest 575 passed / 3 skipped，API 契约 132 paths 不变。未在非隔离库上执行任何 upgrade/downgrade，未接触生产域名、生产实例与真实学生数据；命令原文与数值见 `docs/production/verification.md`。

证件桶不参与普通媒体备份或CDN缓存。恢复数据库后先执行证件清理，再开放核验入口；不得恢复已物理删除的证件对象。备份中的旧身份字段也受访问与保留期控制。

## 后续有序迭代

先完成上述发布门禁，再扩展用户量。视频、支付、私信、多校仍在首版之外。第二学校开放前必须实现并验证学校查询、权限、认证唯一性和缓存隔离。审核工作量超过个人可处理能力时暂停投稿；故障可关闭写入保留浏览。
