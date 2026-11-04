"""守卫 scripts/check_migrations.py 里「链上每条迁移逐条 downgrade/upgrade 往返」的断言。

仓库的迁移链回归原先只逐条覆盖了链尾几条迁移，其余迁移的 downgrade 路径从未在
回归里被执行过。这条断言一旦被删掉、目标 revision 集合写错或对象名写错，
整条链的回滚路径就又失去 CI 覆盖，因此用静态与行为两种方式把它锁住：
静态方式核对迁移链清单与迁移文件逐条对得上（含每条迁移引入/移除的对象名），
行为方式用假数据库验证「逐条降级再逐条升级」确实被执行，且状态不对时断言必须失败。
"""

import asyncio
import importlib.util
import re
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_migrations.py"
VERSIONS = ROOT / "backend" / "alembic" / "versions"


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


migration = module("check_migrations")


def revision_sources():
    """迁移文件里的 revision、父版本与源码。"""
    sources = {}
    for path in sorted(VERSIONS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        revision = re.search(r"^revision(?::\s*str)?\s*=\s*['\"]([0-9a-z]+)['\"]", source, re.M)
        parent = re.search(
            r"^down_revision(?::[^=]+)?\s*=\s*(?:['\"]([0-9a-z]+)['\"]|None)", source, re.M)
        self_revision = revision.group(1)
        sources[self_revision] = (parent.group(1) if parent and parent.group(1) else None,
                                  source, path)
    return sources


def created_pattern(probe):
    """该迁移「引入」的对象，必须能在迁移源码里找到对应的创建动作。"""
    kind = probe[0]
    if kind == "table":
        return r"create_table\(\s*['\"]" + re.escape(probe[1]) + r"['\"]"
    if kind == "column":
        return (r"add_column\(\s*['\"]" + re.escape(probe[1]) + r"['\"]\s*,\s*"
                r"sa\.Column\(\s*['\"]" + re.escape(probe[2]) + r"['\"]")
    if kind == "index":
        return r"create_index\(\s*(?:op\.f\(\s*)?['\"]" + re.escape(probe[1]) + r"['\"]"
    return (r"drop_constraint\(\s*['\"]" + re.escape(probe[2]) + r"['\"]\s*,\s*['\"]"
            + re.escape(probe[1]) + r"['\"]")


class FakeChainDatabase:
    """按迁移链模拟 alembic_version 与各对象的存在状态。"""

    def __init__(self, chain, keep_on_downgrade=(), wrong_version=None):
        self.chain = chain
        self.index = -1
        self.revision = None
        self.present = set()
        self.calls = []
        self.keep_on_downgrade = set(keep_on_downgrade)
        self.wrong_version = wrong_version

    def position(self, revision):
        for index, step in enumerate(self.chain):
            if step.revision == revision:
                return index
        raise AssertionError(f"unknown revision {revision}")

    def introduced_at(self, probe):
        for index, step in enumerate(self.chain):
            if probe in step.introduced:
                return index
        return None

    def removed_at(self, probe):
        for index, step in enumerate(self.chain):
            if probe in step.removed:
                return index
        return None

    def state(self, index):
        present = set()
        probes = {probe for step in self.chain for probe in step.introduced + step.removed}
        for probe in probes:
            introduced = self.introduced_at(probe)
            removed = self.removed_at(probe)
            if introduced is None or introduced > index:
                continue
            if removed is not None and removed <= index:
                continue
            present.add(probe)
        return present

    def migrate(self, *arguments):
        self.calls.append(arguments)
        if arguments[0] == "upgrade":
            target = arguments[1]
            index = len(self.chain) - 1 if target == "head" else self.position(target)
        else:
            target = arguments[1]
            index = -1 if target == migration.BASE_TARGET else self.position(target)
        self.index = index
        self.revision = None if index < 0 else self.chain[index].revision
        self.present = self.state(index)
        if arguments[0] == "downgrade":
            self.present |= self.keep_on_downgrade
        if self.wrong_version is not None:
            self.revision = self.wrong_version

    async def applied_revision(self, url):
        return self.revision

    async def schema_snapshot(self, url):
        return tuple(sorted(self.present))

    async def table_present(self, url, table):
        return ("table", table) in self.present

    async def column_present(self, url, table, column):
        return ("column", table, column) in self.present

    async def index_present(self, url, index):
        return ("index", index) in self.present

    async def constraint_present(self, url, table, constraint):
        return ("constraint", table, constraint) in self.present


SAMPLE_CHAIN = (
    migration.Step("aaa111", None,
                  (("table", "first"), ("constraint", "first", "fk_first")),
                  ()),
    migration.Step("bbb222", "aaa111",
                  (("table", "second"), ("column", "first", "extra")),
                  ()),
    migration.Step("ccc333", "bbb222",
                  (("table", "third"),),
                  (("constraint", "first", "fk_first"),)),
)


def run_roundtrip(database, chain=SAMPLE_CHAIN):
    with patch.object(migration, "migrate", database.migrate), \
            patch.object(migration, "applied_revision", database.applied_revision), \
            patch.object(migration, "schema_snapshot", database.schema_snapshot), \
            patch.object(migration, "table_present", database.table_present), \
            patch.object(migration, "column_present", database.column_present), \
            patch.object(migration, "index_present", database.index_present), \
            patch.object(migration, "constraint_present", database.constraint_present):
        asyncio.run(migration.assert_chain_roundtrips("postgresql://db/sample_migration", chain))


class MigrationChainRoundtripTests(unittest.TestCase):
    def test_chain_covers_every_migration_file_with_the_right_parent(self):
        sources = revision_sources()
        chain = migration.CHAIN
        self.assertEqual({step.revision for step in chain}, set(sources),
                         "the migration chain must list every migration file exactly once")
        for index, step in enumerate(chain):
            self.assertEqual(step.parent, sources[step.revision][0],
                             f"{step.revision} must point at its real parent revision")
            if index:
                self.assertEqual(chain[index - 1].revision, step.parent,
                                 "the chain must be a single linear path")

    def test_declared_objects_exist_in_the_migration_sources(self):
        sources = revision_sources()
        for step in migration.CHAIN:
            source = sources[step.revision][1]
            for probe in step.introduced + step.removed:
                self.assertRegex(source, created_pattern(probe),
                                 f"{step.revision} must really touch {probe}")

    def test_roundtrip_downgrades_and_re_upgrades_every_revision(self):
        database = FakeChainDatabase(SAMPLE_CHAIN)
        run_roundtrip(database)
        for step in SAMPLE_CHAIN:
            target = migration.BASE_TARGET if step.parent is None else step.parent
            self.assertIn(("downgrade", target), database.calls)
            self.assertIn(("upgrade", step.revision), database.calls)
        self.assertEqual(database.revision, SAMPLE_CHAIN[0].revision)

    def test_assertion_fails_when_an_object_survives_the_downgrade(self):
        database = FakeChainDatabase(SAMPLE_CHAIN, keep_on_downgrade={("table", "second")})
        with self.assertRaises(AssertionError):
            run_roundtrip(database)

    def test_assertion_fails_when_alembic_version_does_not_reach_the_parent_revision(self):
        database = FakeChainDatabase(SAMPLE_CHAIN, wrong_version="zzz999")
        with self.assertRaises(AssertionError):
            run_roundtrip(database)

    def test_main_flow_runs_the_chain_roundtrip(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', source)
        main = source.split('if __name__ == "__main__":', 1)[1]
        self.assertIn("assert_chain_roundtrips", main)
        self.assertIn('migrate("check")', main)


if __name__ == "__main__":
    unittest.main()
