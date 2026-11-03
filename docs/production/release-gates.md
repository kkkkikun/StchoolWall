# 生产发布门禁

代码与配置交付完成不等于真实可上架。每个门禁必须保存对应提交、日期、环境、执行人、命令和原始报告；无证据一律保持未通过。shared/release-gates.json 的默认拒绝机制只是发布保险，不能替代审核。

| 门禁 | 必需证据 | 当前状态 |
|---|---|---|
| G0 运营准备 | 真实运营主体/域名、备案和适用资质核查、隐私政策/用户协议/举报渠道、微信和安卓账号/审核材料、真实API域名/COS/审核服务/人工值班人员、预算责任人 | 阻断：需运营方提供；不得填写假凭证 |
| G1 安全 | 关键权限/会话/MFA/证件与媒体隔离测试；依赖/密钥/镜像扫描；零未豁免严重与高危问题；人工越权复核和隐私数据流评审 | 部分通过：主前端与管理台官方 npm audit 均 **0 high / 0 critical**（管理台自 2026-11-01 起 **0 vulnerabilities**；主前端残余 20 moderate 全部来自 devDependency 传递链，不进入客户端产物）；pip-audit、Gitleaks、Trivy 已在 CI 设为硬门禁；pip-audit 于 2026-11-01 因 pillow 12.3.0 的 39 条新 advisory 失败（Pillow 13.0.0 起要求 Python ≥ 3.11，而 12.3.0 是最后一个支持 3.10 的版本），解除方式见 `openspec/changes/backend-python-311/`；Gitleaks、Trivy **本地未执行**；**独立人工安全复核、真实 COS 权限/版本清理检查、腾讯云额度/超时/费用验证、生产密钥与管理员 TOTP 配置仍未完成**。2026-11-02 Production CI 实测（运行 41369377491）：`pip-audit -r backend/requirements.txt --strict` 通过（无已知漏洞）、Gitleaks 密钥扫描通过、**Trivy 镜像扫描实跑并失败** —— 基础镜像 `python:3.11-slim`（Debian 13.7）自带 46 条无修复版本 HIGH，另有镜像内 `setuptools` 内置依赖 2 条 HIGH；扫描失败即中止推送（带高危的镜像未发布），**未豁免、未降门禁**，细节见[验证记录](verification.md)。2026-11-02 已在 `backend/Dockerfile` 的安装层内移除镜像自带的 `setuptools`/`wheel`（运行期用不到的构建工具，其 `_vendor` 内置的 `jaraco.context 5.3.0`、`wheel 0.45.1` 两条 HIGH 随之消失）；**2026-11-03 Production CI 实测（运行 `41578409185`，提交 `e504709`，image 作业 job `125732883940`）已给出该结论的权威证据**：导入冒烟仍打印 `built image imports and exports contract`，Trivy `Report Summary` 里 **65 个 `python-pkg` 目标逐条为 0**，全表 `Total: 45 (HIGH: 45, CRITICAL: 0)` 全部来自 `debian 13.7` 的 OS 层 —— **python-pkg 层 HIGH 已清零**；但 OS 层 **45 条无修复版本 HIGH 仍在**（较 2026-11-02 的 46 条少 1 条），Trivy 退出码 1、`image` 作业失败、带高危的镜像未推送，`openspec/changes/backend-python-311/tasks.md` 第 9 行**保持未勾选**，**未豁免、未降门禁**（未加 `.trivyignore`、未改 severity、未改 `ignore-unfixed`）。OS 层 HIGH 仍需等 Debian 上游安全更新后重建，或走 `openspec/changes/` 提案换镜像族（人工决策），**G1 门禁仍未解除**，细节见[验证记录](verification.md) |
| G2 可靠性 | 相同制品预发布、故障恢复与应用回滚演练、独立迁移与旧版兼容验证、加密异地备份/PITR实测RPO/RTO、告警真实到达并被确认 | 阻断：真实恢复和告警证据未提供。2026-11-02 Production CI 实测（运行 41369377491）：目标 PostgreSQL 15 + Redis 7 环境的后端全量用例（535 passed）与迁移链 upgrade/downgrade/再 upgrade 已在隔离库通过；预发布、真实异机备份恢复、告警到达仍未演练 |
| G3 容量 | 独立环境真实比例数据、1万用户/10万帖/50万评论，100req/s 30分钟、200req/s 5分钟、8小时长稳压测、SQL执行计划、计数/名额一致性与任务恢复报告 | 部分实测：steady 延迟达标、burst 未通过、soak 中止于 92%（未达 8 小时）；**仍未通过**，数值与判定见 `docs/production/capacity.md` |
| G4 三端验收 | Web/微信/Android关键流程真机记录、登录/刷新/注销/权限撤销/拒绝权限/弱网、隐私与举报/申诉闭环、平台审核通过与制品签名 | 外部审核与签名待完成 |
| G5 灰度运行 | 单校白名单灰度、逐级放量、观察告警与审核积压、明确回退阈值和值班人 | 必须 G0..G4 后执行 |

## 首发接受目标

- 所有公开读接口与互动权限匹配；学籍未通过者不能发布/互动；冻结/注销/角色撤销立即影响新请求。
- access token <=15分钟，refresh <=30天，支持轮换、重放撤销和退出；管理员只允许console+MFA+最小权限，导出与证件访问留痕。
- 学籍证件使用独立私有COS桶，证件不进入日志/公共API；撤回、处理后保留期、删除失败重试均可验证。
- 文本/媒体异常保持待审；未审文件不可公开；审核任务可重启恢复、重试、死信与人工重放，业务动作与outbox同事务。
- 核心读API p95≤500ms、写API p95≤800ms、5xx<0.1%，100req/s持续30分钟、200req/s持续5分钟、8小时长稳无持续资源增长；限流429单列，不混成成功吞吐。此前目标是验收目标，不是已测能力。
- 首发月可用性目标99.5%（30天错误预算216分钟），RPO≤1小时，RTO≤4小时。根据实际预算与演练结果调整并记录，不能把配置值当保证。
- 所有发布制品可追踪到同一个commit和image digest；后端、Web、管理端版本组合与上一版兼容；迁移与回滚必须先在预发布演练。

## 发布审核

GitHub production environment 设required reviewers，且填写匹配commit的shared/release-gates.json，G0..G4 evidence指向报告。严重漏洞、恢复失败、未审媒体泄露、权限绕过或会话撤销失败均不得豁免上线。一般风险若业务方接受，单独记录影响、负责人、到期日及补救，不添加“全局忽略扫描”配置。

先开放50人白名单，观察至少一个完整校园高峰和一次人工审核值班周期，再扩至200人，最后全校开放；每阶至少24小时观察。任何权限/隐私事故立即暂停放量；核心5xx>1%持续5分钟、p95>1秒持续10分钟、待审最旧任务>10分钟持续5分钟，回退应用/关闭新增写入并处理故障。
