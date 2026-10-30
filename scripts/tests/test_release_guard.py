import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReleaseGuardTests(unittest.TestCase):
    def test_production_without_gate_evidence_never_calls_docker(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "deploy"
            source = Path(td) / "source"
            source.mkdir()
            (target / "shared").mkdir(parents=True)
            (target / "shared/.env").write_text("DEPLOY_ENVIRONMENT=production\n")
            (target / "shared/release-gates.json").write_text(json.dumps({
                "production_approved": False, "revision": "a" * 40,
            }))
            (source / "manifest.json").write_text(json.dumps({
                "revision": "a" * 40, "backend_image": "ghcr.io/example/schoolwall@sha256:" + "b" * 64,
            }))
            binary = Path(td) / "bin"
            binary.mkdir()
            marker = Path(td) / "docker-was-called"
            (binary / "docker").write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 99\n")
            (binary / "docker").chmod(0o700)
            result = subprocess.run(["bash", str(ROOT / "scripts/rollout.sh"), str(target), str(source)],
                env=dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"]),
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
            self.assertFalse(list((target / "releases").iterdir()))

    def test_unsafe_deployment_root_rejected(self):
        result = subprocess.run(["bash", str(ROOT / "scripts/rollout.sh"), "/", "/tmp"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
