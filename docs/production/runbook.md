# 生产运行与事故处理

此手册面向首发单校运营。负责人、应急联系人和真实告警渠道需要写入受控运行文档；仓库不记录电话号码、云密钥和凭证。首次上线前做桌面演练和实际恢复，保存证据。

## 探针与预算

/health/live 仅判断进程；/health/ready 检查数据库和Redis，故障返回非200；正常响应包含revision用于发布核对。禁止把liveness绑定外部微信/COS，避免供应商故障触发无限重启。Docker健康状态本身不会自动重启unhealthy容器，也不会通知值班人。

deploy/monitoring 提供Prometheus+blackbox+Alertmanager配置。替换真实域名、配置真实receiver后，仅在私有运维网络启动；上线前主动制造一次无害探针失败，确认告警到达、被确认、恢复通知到达。当前receiver是空模板，不属于完成告警。

| 信号 | 首发告警目标 | 处理 |
|---|---|---|
| readiness/liveness | 任一失败1分钟 | 定位进程/DB/Redis，先确认当前commit |
| API | 5xx>1% 5分钟、p95>1秒10分钟 | 暂停放量，记录请求ID，必要时回退 |
| jobs | oldest pending>10分钟5分钟、dead>0、running lease过期 | 检查worker/供应商/配额，修复后有限重放 |
| DB/Redis | pool使用>80% 10分钟、锁等待上升、Redis失败>0 | 查慢SQL/连接预算，禁止盲目加worker |
| 备份 | WAL归档>30分钟或失败增长、最新备份>26小时 | 立即修复备份；未恢复保护前停止新增风险变更 |
| 容量/证书 | 磁盘<20%、内存>85% 10分钟、证书<14天 | 扩容/清理受控制品、续证并检查作业 |

HTTP探针与证书规则已提供；应用RED指标抓取与延迟/5xx规则已提供，仍需真实告警验证；任务、主机、DB、备份指标需要接入对应exporter或应用metrics并验证。不得把表中目标说成所有告警已经配置。jobs初期可在受控只读DB会话执行：
```sql
SELECT status, count(*), min(available_at), min(lease_until)
FROM jobs WHERE status IN ('pending','running','dead') GROUP BY status;
```
只输出聚合，禁止把payload、证件、token或用户内容发到告警渠道。每月按30天99.5%目标计算216分钟错误预算；消耗过半暂停功能发布，耗尽后只做安全/恢复性变更直到复盘确认恢复。

首发恢复验收目标为RPO≤1小时、RTO≤4小时；告警留出恢复处理余量，不能把归档配置当作已满足RPO。

## 故障处置

1. 记录时间、用户影响、部署revision、请求ID，冻结发布与放量。使用发布制品里的compose文件和对应release.env，不从不明工作目录执行默认compose。
2. 检查live/ready、API与worker日志、容器退出原因、DB连接/锁、Redis与磁盘。日志不得包含密码、证件或refresh token。
3. 发布导致故障且数据库保持向后兼容：运行rollback-release.sh回退应用；核对revision、ready和用户读/写闭环。不要自动alembic downgrade生产库。
4. 数据库不可用：核心请求明确503/失败，不把写入伪装成功；恢复依赖后幂等重试。数据损坏按backup/README.md执行隔离恢复，再由负责人批准切换。
5. Redis不可用：限流/会话相关敏感操作停止接受，禁止绕过验证放行；公开DB读取若实现允许可继续。ready会失败，运维不要因此无限重启健康API。
6. 审核/COS/微信不可用：保持待审、有限重试和告警；不降低审核门槛。供应商恢复后处理积压，dead任务经人工确认后重放；不可批量“全通过”。
7. 账户/权限或媒体泄露：收紧入口、撤销受影响会话、保全审计，确认对象私有权限；完成影响面评估、通知责任人与必要处置后恢复。
8. 故障结束记录时间线、数据损失、告警缺口和整改负责人。恢复不等于完成复盘。

## 可信代理与客户端IP

API只映射127.0.0.1:8000，公网入口由宿主Nginx终止TLS；Nginx必须用$remote_addr覆盖X-Forwarded-For，不能追加用户传入的链。Compose为默认bridge设定可配置SCHOOLWALL_SUBNET与SCHOOLWALL_GATEWAY，并把精确gateway注入FORWARDED_ALLOW_IPS；Uvicorn从环境读取，不以CLI写死127.0.0.1。禁止信任*或整个私网网段。首次部署前确认子网不与主机/VPN/其他容器重叠；改变已运行网络需要独立维护窗口。

预发布实际验收时用 docker network inspect schoolwall_default 核对gateway与容器内FORWARDED_ALLOW_IPS相同。分别从两条真实外网连接向web-login发送一次合成不存在账号请求，并从受控Redis核对对应rl:web_login:ip:<已知真实IP>计数；加伪造X-Forwarded-For:203.0.113.99重试，确认真实IP计数增长、伪造IP计数不增长，且bridge网关不会替代所有用户。只查询预先知道的测试IP键，不扫描输出其他用户IP。宿主直接绕过Nginx请求不能对外开放。仓库有实际ASGI proxy middleware回归与静态Nginx/Compose检查；它们不能代替真实DNAT链路验收，未验收保持G2阻断。

## 投稿开关与日志

PUBLISHING_ENABLED=false 是环境级投稿硬限，保留登录、注销和浏览；动态 PUT /api/v1/admin/runtime-controls 用于已授权管理员紧急关闭新投稿，Redis AOF 保存该状态。灾难恢复后必须先核对环境硬限和动态状态，再恢复投稿；Redis恢复或动态开关不能越过环境false。其他敏感互动是否开放按对应权限与事故处置决定，不把投稿开关当作全站只读模式。

Nginx access_log 使用不含query的 schoolwall_safe 模板，禁止换回$request/$request_uri、记录Authorization/Cookie或原始请求体；Nginx原生错误格式无法删除query，因此此站点禁用原生error_log，依靠应用结构日志、指标和探针定位故障。Uvicorn关闭默认access log，应用日志仅记录模板route、请求ID、状态和耗时。上线须用含假code/state的回调请求核对整条日志链，并验证日志轮转和受控保留策略。

## 发布与维护

单机API容器替换可能短暂中断，必须在灰度阶段验证重试体验。发布前检查磁盘、备份新鲜度、异地恢复报告和任务积压，执行唯一迁移任务。至少保留上一套可运行镜像、静态制品和manifest，清理旧制品前确认其未被current/previous引用。配置、存储迁移、证书、密钥轮换和数据库大版本升级各有独立变更记录。

数据库连接总预算 = API副本数 × workers × (DB_POOL_SIZE+DB_MAX_OVERFLOW) + worker + 迁移 + 运维保留。先看实测排队与数据库CPU/IO，再调整连接；默认1 worker与10+10连接每API容器最多20连接。private_media与证件卷不可挂到/static，任何备份/导出都继承相同私有权限。

## 本次复验工具位置

这些目录是当前工作站的忽略缓存，可被清理，不能作为生产依赖或持久证据。最终通过/阻断记录见verification.md；CI需要重新在目标PG15/Redis7和真实镜像执行。

- Python隔离运行时：.pytest_cache/secure-deps/bin/python；依赖兼容检查为 uv pip check --python .pytest_cache/secure-deps/bin/python。uv位于/home/kikun/.local/bin/uv。
- actionlint 1.7.7：.pytest_cache/actionlint/actionlint（同目录保留官方linux_amd64发布压缩包），运行该二进制检查 .github/workflows/ci.yml 和 deploy.yml。
- 当前Windows Docker CLI：D:\Docker\resources\bin\docker.exe，只用于compose config --quiet解析；本地没有运行Docker engine，镜像构建/Trivy/真实容器发布并未完成。
- 当前本地隔离PG14.24/Redis6：127.0.0.1:55432与:56379，数据在 .pytest_cache/production-runtime/pgdata，提取工具在 .pytest_cache/production-runtime/root/usr/lib/postgresql/14/bin 和 root/usr/bin/redis-server；客户端需将root/usr/lib/x86_64-linux-gnu加入LD_LIBRARY_PATH。服务属于临时测试，不触碰开发/生产库。
- 迁移/恢复脚本为 scripts/check_migrations.py 与 scripts/check_restore.py，均要求ENVIRONMENT=test、显式MIGRATION_TEST_ACK、独立*_migration[_test]库；拒绝覆盖已有库。逻辑恢复仅验证合成数据，不构成异地PITR/RPO/RTO证明。
- Python审计：uvx --python .pytest_cache/secure-deps/bin/python pip-audit -r backend/requirements.txt --strict。Gitleaks本地未安装、未执行；密钥与镜像扫描目前是CI强制门禁，不能写成已通过。
