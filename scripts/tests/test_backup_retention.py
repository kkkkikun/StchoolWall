import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("retention", ROOT / "deploy/backup_retention.py")
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class RetentionTests(unittest.TestCase):
    def test_retains_newest_and_ignores_unrelated_partial_and_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            dumps = [directory / f"ey_wall_2026-10-{day:02d}_030000.sql.gz" for day in range(1, 21)]
            for dump in reversed(dumps):
                dump.write_bytes(b"dump")
            other = directory / "unrelated.gz"
            other.write_bytes(b"keep")
            partial = directory / "ey_wall_2026-10-21_030000.sql.gz.partial"
            partial.write_bytes(b"keep")
            linked = directory / "ey_wall_2026-10-22_030000.sql.gz"
            linked.symlink_to(other)
            self.assertEqual(retention.prune(directory, 14), dumps[:6])
            self.assertTrue(all(p.exists() for p in dumps[6:]))
            self.assertTrue(other.exists() and partial.exists() and linked.is_symlink())

    def test_rejects_zero_without_deleting(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                retention.prune(Path(td), 0)


if __name__ == "__main__":
    unittest.main()
