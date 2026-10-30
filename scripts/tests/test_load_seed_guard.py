import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / "load/seed.py"
spec = importlib.util.spec_from_file_location("seed", path)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


class SeedGuardTests(unittest.TestCase):
    @patch.dict(os.environ, {"ALLOW_SYNTHETIC_LOAD_SEED": "YES_ISOLATED_DATABASE"})
    def test_production_and_normal_database_are_rejected(self):
        for environment, database in [
            ("production", "postgresql://db/schoolwall_loadtest"),
            ("development", "postgresql://db/schoolwall_loadtest"),
            ("test", "postgresql://db/ey_wall"),
            ("test", "postgresql://db/ey_wall_test"),
        ]:
            with self.assertRaises(SystemExit):
                seed.validate_target(environment, database)

    @patch.dict(os.environ, {}, clear=True)
    def test_explicit_acknowledgement_required(self):
        with self.assertRaises(SystemExit):
            seed.validate_target("test", "postgresql://db/schoolwall_loadtest")

    @patch.dict(os.environ, {"ALLOW_SYNTHETIC_LOAD_SEED": "YES_ISOLATED_DATABASE"})
    def test_isolated_explicit_database_accepted(self):
        seed.validate_target("test", "postgresql://db/schoolwall_loadtest")
