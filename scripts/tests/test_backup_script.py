import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BackupScriptTests(unittest.TestCase):
    def run_backup(self, fail=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        for name in ("backup.sh", "backup_retention.py", "backup_status.py"):
            shutil.copy(ROOT / "deploy" / name, directory / name)
        backups = directory / "backups"
        backups.mkdir()
        old = [backups / f"ey_wall_2020-01-{d:02d}_000000.sql.gz" for d in range(1, 6)]
        for path in old:
            path.write_bytes(b"old backup")
        binary = directory / "bin"
        binary.mkdir()
        fake = binary / "docker"
        fake.write_text("#!/bin/sh\n" + ("exit 51\n" if fail else "printf 'synthetic SQL dump'\n"))
        fake.chmod(0o700)
        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"], KEEP_BACKUPS="3")
        result = subprocess.run(["bash", str(directory / "backup.sh")], env=env, capture_output=True, text=True)
        return directory, old, result

    def test_success_keeps_newest_three_and_private_output(self):
        directory, old, result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        completed = sorted((directory / "backups").glob("*.sql.gz"))
        self.assertEqual(len(completed), 3)
        self.assertFalse(any(p.exists() for p in old[:3]))
        new = completed[-1]
        self.assertEqual(stat.S_IMODE(new.stat().st_mode), 0o600)
        self.assertEqual(subprocess.run(["gzip", "-t", str(new)]).returncode, 0)

    def test_failed_dump_preserves_all_old_backups_and_removes_partial(self):
        directory, old, result = self.run_backup(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(p.exists() for p in old))
        self.assertFalse(list((directory / "backups").glob("*.partial")))

    def read_status(self, directory: Path) -> dict:
        """读回备份脚本写下的状态文件。"""
        path = directory / "backup-status" / "backup_status.json"
        self.assertTrue(path.exists(), "备份脚本必须写下状态文件")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_a_successful_backup_records_the_status(self):
        """成功的备份必须把「最近一次成功」写进状态文件（应用据此暴露备份新鲜度）。"""
        directory, _, result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        status = self.read_status(directory)
        self.assertTrue(status["last_attempt_ok"])
        self.assertEqual(status["failures"], 0)
        self.assertEqual(status["attempts"], 1)
        self.assertIsNotNone(status["last_success_at"])
        # 状态文件里只有时间戳与计数：没有备份路径、密钥或备份内容。
        self.assertNotIn("backups", json.dumps(status))
        self.assertNotIn(str(directory), json.dumps(status))

    def test_a_failed_backup_records_the_failure(self):
        """失败的备份必须把失败写进状态文件（应用据此暴露备份失败信号）。"""
        directory, _, result = self.run_backup(fail=True)
        self.assertNotEqual(result.returncode, 0)
        status = self.read_status(directory)
        self.assertFalse(status["last_attempt_ok"])
        self.assertEqual(status["failures"], 1)
        self.assertIsNone(status["last_success_at"])

    def test_the_status_file_is_readable_by_the_backend_container(self):
        """状态目录与状态文件要能让后端容器（uid 10001）只读读到。"""
        directory, _, result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        status_dir = directory / "backup-status"
        self.assertTrue(stat.S_IMODE(status_dir.stat().st_mode) & stat.S_IROTH)
        status_file = status_dir / "backup_status.json"
        self.assertTrue(stat.S_IMODE(status_file.stat().st_mode) & stat.S_IROTH)


if __name__ == "__main__":
    unittest.main()
