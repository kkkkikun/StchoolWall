"""守卫 scripts/check_migrations.py 里针对迁移 b7e2c4a91d30 的显式回滚断言。

仓库脚本原先只做 `alembic downgrade -1`，链中间的 b7e2c4a91d30（media_assets.position）
的 downgrade 路径从未在回归里被执行过。这条断言一旦被删掉，或目标 revision / 列名写错，
position 列的真正回滚就又失去 CI 覆盖，因此同时用静态与行为两种方式锁住它。
"""

import asyncio
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_migrations.py"
POSITION_MIGRATION = ROOT / "backend" / "alembic" / "versions" / "b7e2c4a91d30_add_media_asset_position.py"


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


migration = module("check_migrations")


class FakeDatabase:
    """按 migrate() 的调用模拟 alembic_version 与 position 列的状态。"""

    def __init__(self, head="d7e8f9a0b123", column_survives_downgrade=False):
        self.revision = head
        self.column = True
        self.head = head
        self.column_survives_downgrade = column_survives_downgrade
        self.calls = []

    def migrate(self, *arguments):
        self.calls.append(arguments)
        if arguments == ("downgrade", "529bf8becb3f"):
            self.revision = "529bf8becb3f"
            self.column = self.column_survives_downgrade
        elif arguments == ("upgrade", "head"):
            self.revision = self.head
            self.column = True

    async def applied_revision(self, url):
        return self.revision

    async def column_present(self, url, table, column):
        return self.column


class MigrationDowngradeAssertTests(unittest.TestCase):
    def test_targets_match_the_migration_being_guarded(self):
        self.assertEqual(migration.POSITION_REVISION, "b7e2c4a91d30")
        self.assertEqual(migration.CUTOVER_REVISION, "529bf8becb3f")
        self.assertEqual(migration.POSITION_TABLE, "media_assets")
        self.assertEqual(migration.POSITION_COLUMN, "position")
        source = POSITION_MIGRATION.read_text(encoding="utf-8")
        self.assertIn("revision: str = 'b7e2c4a91d30'", source)
        self.assertIn("down_revision: Union[str, None] = '529bf8becb3f'", source)
        self.assertIn("op.drop_column('media_assets', 'position')", source)

    def test_explicit_rollback_downgrades_to_the_parent_revision_and_re_upgrades(self):
        database = FakeDatabase()
        with patch.object(migration, "migrate", database.migrate), \
                patch.object(migration, "applied_revision", database.applied_revision), \
                patch.object(migration, "column_present", database.column_present):
            asyncio.run(migration.assert_position_rollback("postgresql://db/sample_migration"))
        self.assertIn(("downgrade", "529bf8becb3f"), database.calls)
        self.assertIn(("upgrade", "head"), database.calls)
        self.assertLess(database.calls.index(("downgrade", "529bf8becb3f")),
                        database.calls.index(("upgrade", "head")))

    def test_assertion_fails_when_the_column_survives_the_downgrade(self):
        database = FakeDatabase(column_survives_downgrade=True)
        with patch.object(migration, "migrate", database.migrate), \
                patch.object(migration, "applied_revision", database.applied_revision), \
                patch.object(migration, "column_present", database.column_present):
            with self.assertRaises(AssertionError):
                asyncio.run(migration.assert_position_rollback("postgresql://db/sample_migration"))

    def test_assertion_fails_when_alembic_version_does_not_reach_the_parent_revision(self):
        database = FakeDatabase()

        def wrong_version(*arguments):
            database.calls.append(arguments)
            if arguments == ("downgrade", "529bf8becb3f"):
                database.revision = "d4e6f8a1b357"
                database.column = False

        with patch.object(migration, "migrate", wrong_version), \
                patch.object(migration, "applied_revision", database.applied_revision), \
                patch.object(migration, "column_present", database.column_present):
            with self.assertRaises(AssertionError):
                asyncio.run(migration.assert_position_rollback("postgresql://db/sample_migration"))

    def test_main_flow_runs_the_explicit_rollback(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', source)
        main = source.split('if __name__ == "__main__":', 1)[1]
        self.assertIn("assert_position_rollback", main)
        self.assertIn('migrate("check")', main)


if __name__ == "__main__":
    unittest.main()
