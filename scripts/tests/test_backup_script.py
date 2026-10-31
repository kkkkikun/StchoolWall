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
        for name in ("backup.sh", "backup_retention.py"):
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


if __name__ == "__main__":
    unittest.main()
