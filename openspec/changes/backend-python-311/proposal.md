# 后端运行时升到 Python 3.11 并跟进 Pillow 13

## Why

2026-11-01 新披露的 Pillow advisory 让 CI 硬门禁 `pip-audit --strict` 失败：pillow 12.3.0 命中 39 条 advisory（堆越界、越界读、内存泄露、解压炸弹绕过、ReDoS、参数注入等，含高危），修复版本统一指向 13.0.0。而 Pillow 13.0.0 的 `requires_python` 是 `>=3.11`，Pillow 12.3.0 已是最后一个支持 Python 3.10 的版本 —— 在 Python 3.10 上不存在可用修复版。按 `docs/production/release-gates.md` 的 G1 规则（严重与高危漏洞不得豁免上线），唯一合规的解除方式是升级运行时。升级前该门禁在 main 上同样是红的，任何 PR 都无法通过门禁合并。

## What Changes

- 后端运行时 Python 3.10 → 3.11，CI（`.github/workflows/ci.yml`）、后端镜像（`backend/Dockerfile`）、服务器侧 CI 镜像（`deploy/ci/Dockerfile.backend-ci`）同步。
- `backend/requirements.txt`：`Pillow==12.3.0` → `Pillow==13.0.0`。
- 同步版本记录：`README.md`、`openspec/config.yaml`、`openspec/specs/references/spec.md`、`.claude/docs/SNAPSHOT.md`、`deploy/ci/README.md`。
- 不改业务代码、API 契约、数据库结构、compose/nginx/发布回滚脚本与任何密钥配置。

## Impact

- 影响面只有后端进程与镜像的解释器版本；业务逻辑、接口、数据与存储格式不变。
- 本地实测（Python 3.11.15 + Pillow 13.0.0）：`app.main` 可导入并导出 125 条 OpenAPI 路径；`normalize_image` 与 `sanitize_proof_image` 行为一致（去 EXIF、拒绝非法图片、尺寸与像素限制照旧生效）。
- 验证边界：后端全量 pytest 与迁移链需要真实 PostgreSQL 15 / Redis 7，由 Production CI 判定；镜像构建需要 Docker 环境，由 CI 的 image 作业判定。
- 未部署、未提交任何平台审核，未签署任何运营方政策。
