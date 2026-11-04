"""守卫 API 契约导出与入库快照 `release/openapi.json` 的比对。

仓库文档把「接口面不得变化、契约 paths 数保持不变」当成既定不变量，
但导出脚本原先只校验必备端点与密钥字段，随后就把契约写回入库快照 ——
它覆盖快照、从不与快照比对，接口面的静默漂移没有任何门禁能发现。

本守卫用例在临时目录里放一个替身后端（只返回给定契约），跑真实脚本，
锁住三件事：比对确实存在、打印的路径数与入库快照一致、比对失败时退出码非 0。
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_api_contract.py"
SNAPSHOT = ROOT / "release/openapi.json"

# 替身后端：脚本只要求 app.main.app.openapi() 返回契约，不碰数据库与外部服务。
STUB_BACKEND = '''import json
import os

CONTRACT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "contract.json")


class StubApp:
    def openapi(self):
        with open(CONTRACT_PATH, encoding="utf-8") as handle:
            return json.load(handle)


app = StubApp()
'''


def snapshot_contract() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


class ApiContractSnapshotGuardTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        (self.root / "scripts").mkdir()
        (self.root / "backend/app").mkdir(parents=True)
        (self.root / "release").mkdir()
        (self.root / "backend/app/__init__.py").write_text("", encoding="utf-8")
        (self.root / "backend/app/main.py").write_text(STUB_BACKEND, encoding="utf-8")
        shutil.copyfile(SCRIPT, self.root / "scripts/check_api_contract.py")
        shutil.copyfile(SNAPSHOT, self.root / "release/openapi.json")
        self.output = self.root / "out/openapi.json"

    def run_guard(self, contract: dict, *extra_args: str, output: Path | None = None) -> subprocess.CompletedProcess:
        (self.root / "contract.json").write_text(
            json.dumps(contract, ensure_ascii=False), encoding="utf-8"
        )
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/check_api_contract.py"),
             "--output", str(output or self.output), *extra_args],
            capture_output=True, text=True,
        )

    def snapshot_file(self) -> Path:
        return self.root / "release/openapi.json"

    def test_guard_compares_the_export_with_the_committed_snapshot(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("release/openapi.json", source, "守卫脚本必须指向入库快照")
        self.assertIn("compare_with_snapshot(", source, "守卫脚本必须调用与快照的比对")
        result = self.run_guard(snapshot_contract())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exported_path_count_matches_the_committed_snapshot(self):
        contract = snapshot_contract()
        result = self.run_guard(contract)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"contract validated: {len(contract['paths'])} paths", result.stdout)
        # 路径数只能来自入库快照，不能在守卫脚本里写死成常量。
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIsNone(
            re.search(rf"\b{len(contract['paths'])}\b", source),
            "守卫脚本不得把契约路径数写死成常量",
        )

    def test_added_path_fails_with_nonzero_exit(self):
        contract = snapshot_contract()
        contract["paths"]["/api/v1/guard-added"] = {
            "get": {"responses": {"200": {"description": "ok"}}}
        }
        result = self.run_guard(contract)
        self.assertNotEqual(result.returncode, 0, "新增路径必须立刻失败")
        self.assertIn("/api/v1/guard-added", result.stdout + result.stderr)
        self.assertFalse(self.output.exists(), "比对失败时不得写出契约文件")
        self.assertEqual(
            self.snapshot_file().read_bytes(), SNAPSHOT.read_bytes(),
            "比对失败时不得改写入库快照",
        )

    def test_removed_path_fails_with_nonzero_exit(self):
        contract = snapshot_contract()
        removed = next(path for path in contract["paths"] if path.startswith("/api/v1/"))
        del contract["paths"][removed]
        result = self.run_guard(contract)
        self.assertNotEqual(result.returncode, 0, "删除路径必须立刻失败")
        self.assertIn(removed, result.stdout + result.stderr)

    def test_changed_method_fails_with_nonzero_exit(self):
        contract = snapshot_contract()
        path = next(
            path for path, operations in contract["paths"].items()
            if len([name for name in operations if name in {"get", "post", "put", "delete"}]) >= 2
        )
        dropped = sorted(
            name for name in contract["paths"][path]
            if name in {"get", "post", "put", "delete"}
        )[-1]
        del contract["paths"][path][dropped]
        result = self.run_guard(contract)
        self.assertNotEqual(result.returncode, 0, "方法集合变化必须立刻失败")
        self.assertIn(path, result.stdout + result.stderr)
        self.assertIn(dropped, result.stdout + result.stderr)

    def test_update_snapshot_refreshes_the_committed_snapshot_on_purpose(self):
        contract = snapshot_contract()
        contract["paths"]["/api/v1/guard-added"] = {
            "get": {"responses": {"200": {"description": "ok"}}}
        }
        result = self.run_guard(contract, "--update-snapshot", output=self.snapshot_file())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        refreshed = json.loads(self.snapshot_file().read_text(encoding="utf-8"))
        self.assertIn("/api/v1/guard-added", refreshed["paths"])

    def test_update_snapshot_requires_the_output_to_be_the_snapshot(self):
        result = self.run_guard(snapshot_contract(), "--update-snapshot")
        self.assertNotEqual(result.returncode, 0, "刷新快照必须显式指向入库快照")
        self.assertIn("release/openapi.json", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
