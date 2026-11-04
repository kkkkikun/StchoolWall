# SchoolWall 可审核的生产发布

此目录提供单校、单机起步的发布工具，不代表生产已上线。真实域名、备案/资质、微信审核、COS/腾讯审核凭证、告警接收人及备份恢复报告均需要运营者配置并验收。入口为 [发布门禁](../docs/production/release-gates.md)、[运行手册](../docs/production/runbook.md)、[容量验证](../docs/production/capacity.md)。

## 一次性准备

- 预发布与生产使用隔离主机/数据库/Redis/COS桶和密钥；预发布数据必须脱敏。
- 每台主机安装 Docker Compose v2、Python3、curl、flock、Nginx、TLS；预建 /opt/schoolwall/{incoming,releases,shared}，赋给专用部署账号。部署账号能管理 Docker，属于高权限账号，SSH密钥只保存在对应 GitHub environment secret。
- 复制 env.prod.example 到 shared/.env，权限0600；替换占位符。预发布额外写 DEPLOY_ENVIRONMENT=staging；应用 ENVIRONMENT 仍为 production，验证同样的安全闸门。
- 注册私有 GHCR 的主机只读拉取凭证。CI 使用 GITHUB_TOKEN 推送，不把读写仓库凭证放进应用环境。
- 备份接入见 [pgBackRest](backup/README.md)。现有本地上传卷需要设置安全目录权限；新版容器 uid10001。将历史数据在维护窗口备份后迁移，禁止直接修改生产卷并宣称验证完成。
- 逻辑备份（`deploy/backup.sh`）每次尝试都会把结果写进状态目录 `BACKUP_STATUS_DIR`（默认 `backup-status`，**只含时间戳与计数**，没有备份路径、密钥或备份内容）。生产把该目录放在宿主机上，compose 用同一个 `BACKUP_STATUS_DIR`（绝对路径，例如 `/opt/schoolwall/backup-status`，确保部署账号可写、容器 uid10001 可读）；compose 已按只读方式挂载它并把容器内的 `BACKUP_STATUS_FILE` 指向 `/data/backup-status/backup_status.json`。没接上时应用会暴露「备份状态不可读」并触发 `SchoolWallBackupStatusUnknown` 告警 —— 不会静默。
- 监控栈（`deploy/monitoring/`）：仓库提供 Prometheus + blackbox + node_exporter + postgres_exporter + Alertmanager 的配置。node_exporter 采集宿主机的磁盘可用空间与内存使用率，compose 里已把宿主机根目录以只读方式挂到 `/host` 并用 `--path.rootfs=/host` 采集，监听地址只绑 `127.0.0.1:9100`（别暴露到公网，要看指标走已认证的 SSH 隧道）。postgres_exporter 采集数据库的锁与会话等待信号（`pg_stat_activity_count` / `pg_stat_database_deadlocks` / `pg_locks_count`），监听地址只绑 `127.0.0.1:9187`。**exporter 在宿主机上的实际部署、挂载路径与按机型调整磁盘/内存/锁等待阈值属运维安排**，仓库只提供配置与规则；告警接收端同样是空模板，装真实 receiver 并确认告警到达之前不算完成告警。
- postgres_exporter 的连接串与口令**只走只读的运行时配置、绝不入库**：compose 里 `DATA_SOURCE_URI` 只写主机、端口与库名（默认 `127.0.0.1:5432/schoolwall?sslmode=disable`，可用 `POSTGRES_EXPORTER_URI` 覆盖），用户名与口令分别放在宿主机 secret 目录下的两个文件里，以只读方式挂进容器（`DATA_SOURCE_USER_FILE` / `DATA_SOURCE_PASS_FILE`）。在宿主机上准备该目录（默认 `/opt/schoolwall/shared/postgres-exporter`，可用 `POSTGRES_EXPORTER_SECRET_DIR` 覆盖）：`user` 文件写监控账号名、`pass` 文件写口令，**目录与文件要能让容器内的 uid 65534 读到**（例如目录 0755、两个文件 0644；或把属组交给 65534 并用 0750/0640）。监控账号需要 `pg_monitor` 角色（否则读不到 `pg_stat_activity` 的等待事件）与目标库的 CONNECT 权限。仓库里**不得**出现任何口令、连接串或 secret 文件。
- Nginx 使用 nginx.schoolwall.conf，将域名替换、签发 HTTPS 证书；新静态根目录为 /opt/schoolwall/current/web/{h5,admin}。首次发布前符号链接不存在，站点暂时不可用属初始化状态。
- GitHub: branch protection 要求 Production CI 成功；staging 和 production environment 分别设置 SERVER_HOST、SERVER_USERNAME、SERVER_SSH_KEY、SERVER_KNOWN_HOSTS；production 设置 required reviewers 和保护 main。PUBLIC_API_BASE_URL 变量必须是真实 HTTPS API地址，否则小程序制品不能上架。
- 生产发布每次复制 release-gates.example.json 到 shared/release-gates.json，填写匹配 commit、审核人、时间与 G0..G4 证据；默认 false 会阻止发布。

## 发布与回滚

Production CI 执行后端、操作脚本测试、真实 Alembic 迁移链检查、OpenAPI契约、依赖和密钥扫描、H5/微信小程序/Android代码包/后台构建、最终镜像扫描。验证运行的完整Python依赖约束随制品保存，镜像按同一约束安装并执行导入/契约烟测，通过扫描后才推送不可变镜像digest。Android代码包仍需在平台工具中使用真实签名打包和真机审核。部署工作流下载同一 CI 的制品和manifest，在预发布部署，再通过 production environment 发放相同制品。不会在服务器 git pull 或重新编译。

scripts/rollout.sh 加主机级锁，拉取image，停止worker，单独执行一次迁移，再启动API/worker；检查 readiness 和返回的 commit 后原子切换静态站点链接。失败自动恢复上版应用镜像。数据库不会自动降级，所以每次发布必须采用兼容旧应用的 expand/contract 迁移，并在预发布确认恢复旧应用仍能运行。首次单机容器替换存在短暂连接中断，没有宣称零停机。

手工应用回退使用 `bash /path/to/repository/scripts/rollback-release.sh /opt/schoolwall`；只回退应用。破坏性数据库变更、PG大版本升级、bucket迁移属于独立维护变更，不能交给自动回退。不要通过再次运行旧的git源码部署脚本覆盖新制品。旧 deploy/ci/ 脚本保留用于已有环境，生产门禁由 GitHub工作流负责。

镜像/依赖扫描需要联网，首次执行可能暴露原有高危依赖，此时管线应失败。修复/升级后重新出制品；禁止为赶上线全局忽略高危项。当前仓库执行环境没有可用Docker引擎、官方凭证或外部生产环境，真实扫描/容器部署/恢复证明仍需 CI 与运营方提供。
