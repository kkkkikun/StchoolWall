"""守卫 scripts/check_migrations.py 里「整链升级不丢旧版数据」的断言。

仓库的迁移链回归原先只在切换迁移 529bf8becb3f 前后校验过一次旧版夹具，整链升级路径上
旧数据的保全从未被断言过 —— 任一条迁移若在 upgrade 里改坏或丢弃旧数据，回归不会发现。
这条断言一旦被删掉、夹具字段名写错，或「只允许声明过的语义变化」的白名单被放宽，
旧版数据的保全就又失去 CI 覆盖，因此用静态与行为两种方式把它锁住：
静态方式核对夹具只用链底已有的列、白名单与迁移源码一致；
行为方式用假数据库验证「逐条升级再逐条回退都断言旧数据」，且旧数据被改坏、
被丢弃或发生未声明的语义变化时断言必须失败。
"""

import asyncio
import copy
import importlib.util
import re
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_migrations.py"
VERSIONS = ROOT / "backend" / "alembic" / "versions"
BASE_MIGRATION = VERSIONS / "61edfd32690b_init_tables.py"
CUTOVER_MIGRATION = VERSIONS / "529bf8becb3f_production_accounts_verification_media_.py"
REPORT_FK_MIGRATION = VERSIONS / "d4e5f6a7b910_drop_reports_handled_by_fk.py"


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


migration = module("check_migrations")


def base_table_columns(table):
    """链底迁移里某张表创建时的列。"""
    source = BASE_MIGRATION.read_text(encoding="utf-8")
    block = re.search(r"op\.create_table\('" + re.escape(table) + r"',(.*?)\n    \)", source, re.S)
    assert block, f"the chain base must create the {table} table"
    return set(re.findall(r"sa\.Column\('([^']+)'", block.group(1)))


FIXTURES = {
    "post_user_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
    "post_id": 4242,
    "tag_id": 77,
    "reporter_id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
    "report_id": 5151,
}


class FakeLegacyDatabase:
    """按迁移链模拟旧版夹具的状态。

    只有白名单声明过的语义变化才会改动旧数据；``corrupt_revision`` / ``drop_revision``
    用来模拟「某条迁移把旧数据改坏或丢弃」，此时断言必须失败。
    """

    def __init__(self, corrupt_revision=None, drop_revision=None, corrupt_table="users"):
        self.state = migration.legacy_expectation(FIXTURES)
        self.corrupt_revision = corrupt_revision
        self.drop_revision = drop_revision
        self.corrupt_table = corrupt_table
        self.calls = []

    def migrate(self, *arguments):
        self.calls.append(arguments)
        direction, target = arguments[0], arguments[1]
        if direction == "upgrade" and target == migration.CUTOVER_REVISION:
            self.state = migration.cutover_effect(self.state)
        if direction == "downgrade" and target == "c3d4e5f6a809":
            self.state = migration.report_cleanup_effect(self.state)
        if target == self.corrupt_revision:
            self.state["users"][0] = dict(self.state["users"][0], nickname="corrupted")
        if target == self.drop_revision:
            self.state[self.corrupt_table] = []

    async def insert_legacy_fixture(self, url):
        return FIXTURES

    async def fetch_legacy_state(self, url):
        return copy.deepcopy(self.state)

    async def apply_legacy_state_adjustment(self, url, fixtures, step, direction):
        return None


def run_guard(database):
    with patch.object(migration, "migrate", database.migrate), \
            patch.object(migration, "insert_legacy_fixture", database.insert_legacy_fixture), \
            patch.object(migration, "fetch_legacy_state", database.fetch_legacy_state), \
            patch.object(migration, "apply_legacy_state_adjustment",
                         database.apply_legacy_state_adjustment):
        asyncio.run(migration.assert_legacy_data_survives_chain(
            "postgresql://db/sample_migration"))


class MigrationLegacyDataGuardTests(unittest.TestCase):
    def test_fixture_only_uses_columns_of_the_chain_base(self):
        columns = {
            "users": migration.LEGACY_USER_COLUMNS,
            "posts": migration.LEGACY_POST_COLUMNS,
            "tags": migration.LEGACY_TAG_COLUMNS,
            "post_tags": migration.LEGACY_POST_TAG_COLUMNS,
            "reports": migration.LEGACY_REPORT_COLUMNS,
        }
        for table, used in columns.items():
            available = base_table_columns(table)
            self.assertTrue(set(used) <= available,
                            f"the legacy fixture must only use columns the chain base has: "
                            f"{sorted(set(used) - available)} are missing on {table}")
        self.assertEqual(migration.LEGACY_BASE_REVISION, "61edfd32690b")
        self.assertEqual(migration.CHAIN[0].revision, migration.LEGACY_BASE_REVISION)

    def test_fixture_carries_only_synthetic_personal_data(self):
        for spec in migration.LEGACY_USERS:
            self.assertTrue(spec.student_id.startswith("synthetic-"))
            self.assertTrue(spec.real_name.startswith("synthetic-"))
            self.assertNotIn(spec.nickname.lower(), ("", "real"))

    def test_legacy_content_belongs_to_the_account_the_cutover_disables(self):
        openids = [spec.openid for spec in migration.LEGACY_USERS]
        self.assertIn(migration.LEGACY_AUTHOR_OPENID, openids)
        self.assertIn(migration.LEGACY_AUTHOR_OPENID, migration.DEV_DEMO_OPENIDS)

    def test_semantic_change_whitelist_matches_the_migration_sources(self):
        self.assertEqual({key for key in migration.SEMANTIC_CHANGES},
                         {("529bf8becb3f", "upgrade"), ("d4e5f6a7b910", "downgrade")})
        for revision, _ in migration.SEMANTIC_CHANGES:
            self.assertIn(revision, {step.revision for step in migration.CHAIN})
        cutover = CUTOVER_MIGRATION.read_text(encoding="utf-8")
        self.assertIn("student_id = NULL", cutover)
        self.assertIn("real_name = NULL", cutover)
        self.assertIn("is_verified = false", cutover)
        report_fk = REPORT_FK_MIGRATION.read_text(encoding="utf-8")
        self.assertIn("DELETE FROM reports", report_fk)

    def test_guard_asserts_the_legacy_data_on_every_revision(self):
        database = FakeLegacyDatabase()
        run_guard(database)
        for step in migration.CHAIN:
            self.assertIn(("upgrade", step.revision), database.calls)
        for step in migration.CHAIN[1:]:
            self.assertIn(("downgrade", step.parent), database.calls)
        self.assertIn(("downgrade", migration.BASE_TARGET), database.calls)

    def test_assertion_fails_when_a_migration_changes_legacy_data(self):
        database = FakeLegacyDatabase(corrupt_revision="c2b4f6a8d910")
        with self.assertRaises(AssertionError):
            run_guard(database)

    def test_assertion_fails_when_a_migration_drops_legacy_rows(self):
        database = FakeLegacyDatabase(drop_revision="f7a9c2d4e506", corrupt_table="posts")
        with self.assertRaises(AssertionError):
            run_guard(database)

    def test_assertion_fails_when_a_declared_change_is_not_whitelisted(self):
        database = FakeLegacyDatabase()
        whitelist = {key: value for key, value in migration.SEMANTIC_CHANGES.items()
                     if key != ("529bf8becb3f", "upgrade")}
        with patch.dict(migration.SEMANTIC_CHANGES, whitelist, clear=True):
            with self.assertRaises(AssertionError):
                run_guard(database)

    def test_main_flow_runs_the_legacy_data_guard(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', source)
        main = source.split('if __name__ == "__main__":', 1)[1]
        self.assertIn("assert_legacy_data_survives_chain", main)
        self.assertIn('migrate("check")', main)
        self.assertIn("legacy fixture rows and key fields preserved", source)


if __name__ == "__main__":
    unittest.main()
