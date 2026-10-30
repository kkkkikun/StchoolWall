import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

migration = module("check_migrations")
restore = module("check_restore")

class MigrationRestoreGuardTests(unittest.TestCase):
    def test_production_or_regular_database_rejected_before_connecting(self):
        for environment, database in [("production", "sample_migration"),
                                      ("test", "ey_wall"), ("test", "sample_test")]:
            with patch.dict(os.environ, {"ENVIRONMENT": environment,
                 "MIGRATION_TEST_ACK": "YES_ISOLATED_DATABASE",
                 "DATABASE_URL": "postgresql+asyncpg://db/" + database}, clear=True):
                for operation in (migration.guard, restore.guarded_urls):
                    with self.assertRaises(SystemExit):
                        operation()

    def test_missing_acknowledgement_rejected(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "test",
              "DATABASE_URL": "postgresql://db/sample_migration_test"}, clear=True):
            for operation in (migration.guard, restore.guarded_urls):
                with self.assertRaises(SystemExit):
                    operation()

    def test_restore_target_is_a_separate_named_test_database(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "test",
             "MIGRATION_TEST_ACK": "YES_ISOLATED_DATABASE",
             "DATABASE_URL": "postgresql+asyncpg://db/sample_migration_test"}, clear=True):
            source_url, target_url, source, target = restore.guarded_urls()
            self.assertEqual(source, "sample_migration_test")
            self.assertEqual(target, "sample_migration_test_restore_test")
            self.assertNotEqual(source_url, target_url)
            self.assertEqual(migration.guard(), source_url)

    def test_sql_metacharacters_in_source_database_rejected(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "test",
             "MIGRATION_TEST_ACK": "YES_ISOLATED_DATABASE",
             "DATABASE_URL": 'postgresql://db/name";drop_migration_test'}, clear=True):
            with self.assertRaises(SystemExit):
                restore.guarded_urls()
