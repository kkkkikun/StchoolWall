# 实施与验收

- [x] `backend/requirements.txt`：`Pillow==12.3.0` → `Pillow==13.0.0`
- [x] CI 运行时 Python 3.10 → 3.11（`.github/workflows/ci.yml` 的 `setup-python`）
- [x] `backend/Dockerfile` 与 `deploy/ci/Dockerfile.backend-ci` 基础镜像 `python:3.10-slim` → `python:3.11-slim`
- [x] 版本记录同步：`README.md`、`openspec/config.yaml`、`openspec/specs/references/spec.md`、`.claude/docs/SNAPSHOT.md`、`deploy/ci/README.md`
- [x] 本地验证（Python 3.11.15 + Pillow 13.0.0）：`pip-audit -r backend/requirements.txt --strict` 通过；`app.main` 导入成功并导出 125 条路径；`normalize_image` / `sanitize_proof_image` 去 EXIF、拒绝非法图片与尺寸限制行为一致
- [ ] Production CI：PostgreSQL 15 + Redis 7 上的后端全量 pytest、迁移 upgrade/downgrade、API 契约导出与 pip-audit 硬门禁全部通过
- [ ] image 作业（仅 main 分支）：`python:3.11-slim` 基础镜像构建、导入冒烟与 Trivy 扫描通过

验收证据写入 `docs/production/verification.md`；未取得的外部证据保持未勾选。
