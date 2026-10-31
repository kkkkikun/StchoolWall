import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40
IMAGE = "ghcr.io/example/schoolwall@sha256:" + "b" * 64


class RolloutTests(unittest.TestCase):
    def prepare(self, previous=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        target, source, binary = base / "deploy", base / "source", base / "bin"
        for directory in (target / "shared", source / "deploy", source / "web/h5", binary):
            directory.mkdir(parents=True)
        (target / "shared/.env").write_text("DEPLOY_ENVIRONMENT=staging\nAPI_PORT=8000\n")
        (source / "manifest.json").write_text(json.dumps({"revision": REVISION, "backend_image": IMAGE}))
        (source / "deploy/docker-compose.prod.yml").write_text("services: {}\n")
        (source / "web/h5/index.html").write_text("verified web")
        trace = base / "commands"
        (binary / "docker").write_text("""#!/bin/sh
printf '%s\\n' "$*" >> "$TRACE"
case "$*" in
  *"run --rm migrate"*) [ "$FAIL_MIGRATION" != 1 ] || exit 17 ;;
  *"ps --status running -q worker"*) echo worker-container ;;
esac
""")
        (binary / "curl").write_text("""#!/bin/sh
case "$*" in
  *health/live*) printf '{"status":"ok","revision":"%s"}' "$FAKE_REVISION" ;;
  *) printf '{"status":"ok"}' ;;
esac
""")
        for name in ("docker", "curl"):
            (binary / name).chmod(0o700)
        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                   TRACE=str(trace), FAKE_REVISION=REVISION, FAIL_MIGRATION="0")
        old = None
        if previous:
            old = target / "releases" / ("c" * 40)
            (old / "deploy").mkdir(parents=True)
            (old / "release.env").write_text("BACKEND_IMAGE=old@sha256:old\nBUILD_REVISION=old\n")
            (old / "deploy/docker-compose.prod.yml").write_text("services: {}\n")
            (target / "current").symlink_to(old)
        return target, source, env, trace, old

    def test_verified_artifact_migrates_once_and_switches_static_atomically(self):
        target, source, env, trace, _ = self.prepare()
        result = subprocess.run(["bash", str(ROOT / "scripts/rollout.sh"), str(target), str(source)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / "current").resolve(), target / "releases" / REVISION)
        self.assertEqual(trace.read_text().count("run --rm migrate"), 1)
        self.assertLess(trace.read_text().index("run --rm migrate"), trace.read_text().index("up -d --no-build backend worker"))
        # Retry is idempotent for the identical immutable manifest.
        retry = subprocess.run(["bash", str(ROOT / "scripts/rollout.sh"), str(target), str(source)],
                               env=env, capture_output=True, text=True)
        self.assertEqual(retry.returncode, 0, retry.stderr)

    def test_failed_migration_recovers_old_application_without_db_downgrade(self):
        target, source, env, trace, old = self.prepare(previous=True)
        env["FAIL_MIGRATION"] = "1"
        result = subprocess.run(["bash", str(ROOT / "scripts/rollout.sh"), str(target), str(source)],
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((target / "current").resolve(), old)
        commands = trace.read_text().splitlines()
        self.assertIn(str(old / "release.env"), commands[-1])
        self.assertIn("up -d --no-build backend worker", commands[-1])
        self.assertNotIn("downgrade", trace.read_text())


if __name__ == "__main__":
    unittest.main()
