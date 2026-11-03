# 实施与验收

- [x] `backend/requirements.txt`：`Pillow==12.3.0` → `Pillow==13.0.0`
- [x] CI 运行时 Python 3.10 → 3.11（`.github/workflows/ci.yml` 的 `setup-python`）
- [x] `backend/Dockerfile` 与 `deploy/ci/Dockerfile.backend-ci` 基础镜像 `python:3.10-slim` → `python:3.11-slim`
- [x] 版本记录同步：`README.md`、`openspec/config.yaml`、`openspec/specs/references/spec.md`、`.claude/docs/SNAPSHOT.md`、`deploy/ci/README.md`
- [x] 本地验证（Python 3.11.15 + Pillow 13.0.0）：`pip-audit -r backend/requirements.txt --strict` 通过；`app.main` 导入成功并导出 125 条路径；`normalize_image` / `sanitize_proof_image` 去 EXIF、拒绝非法图片与尺寸限制行为一致
- [x] Production CI：PostgreSQL 15 + Redis 7 上的后端全量 pytest、迁移 upgrade/downgrade、API 契约导出与 pip-audit 硬门禁全部通过（2026-11-02 实测：Production CI 运行 41369377491 的 verify 作业全绿 —— pytest 535 passed / 3 skipped、迁移链 upgrade→downgrade→再 upgrade 与 alembic check PASS、逻辑恢复 PASS、契约导出 125 paths、pip-audit --strict 无已知漏洞；命令、环境与原始日志见 `docs/production/verification.md`）
- [ ] image 作业（仅 main 分支）：`python:3.11-slim` 基础镜像构建、导入冒烟与 Trivy 扫描通过（2026-11-03 实测：main 分支 Production CI 运行 `41578409185`（提交 `e504709`，image 作业 job `125732883940`）的原始日志 —— 构建与导入冒烟通过（仍打印 `built image imports and exports contract`），**Trivy 报告里 65 个 `python-pkg` 目标逐条为 0，全表 `Total: 45 (HIGH: 45, CRITICAL: 0)` 全部来自基础镜像 Debian 13.7 的 OS 层**，即镜像内 setuptools/wheel 那 2 条 HIGH（`jaraco.context 5.3.0`、`wheel 0.45.1`）已随 `backend/Dockerfile` 安装层内移除构建期工具而清零；但 OS 层仍有 **45 条无修复版本 HIGH**，Trivy 退出码 1、`image` 作业失败且镜像未推送，故本行**保持未勾选**；未豁免（未加 `.trivyignore`、未改 severity、未改 `ignore-unfixed`），原始日志与命令见 `docs/production/verification.md`。OS 层 HIGH 需等 Debian 上游安全更新或走 `openspec/changes/` 提案与人工决策）

验收证据写入 `docs/production/verification.md`；未取得的外部证据保持未勾选。
