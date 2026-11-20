import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40
IMAGE = "ghcr.io/example/schoolwall@sha256:" + "b" * 64
OLD_IMAGE = "ghcr.io/example/schoolwall@sha256:" + "c" * 64
OLD_REVISION = "d" * 40


class CnRolloutTests(unittest.TestCase):
    def prepare(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        target, source, binary = base / "deploy", base / "source", base / "bin"
        for directory in (target / "shared", source / "deploy", binary):
            directory.mkdir(parents=True)
        for area in ("h5", "admin", "pc"):
            (target / "web" / area).mkdir(parents=True)
            (target / "web" / area / "index.html").write_text("old " + area)
        for area in ("h5", "admin"):
            (source / "web" / area).mkdir(parents=True)
            (source / "web" / area / "index.html").write_text("new " + area)
        (target / "shared/.env").write_text("DEPLOY_ENVIRONMENT=staging\n")
        (source / "manifest.json").write_text(json.dumps({"revision": REVISION, "backend_image": IMAGE}))
        (source / "deploy/docker-compose.cn.yml").write_text("services: {}\n")
        trace = base / "commands"
        (binary / "docker").write_text(f"""#!/bin/sh
printf '%s BACKEND_IMAGE=%s\\n' "$*" "$BACKEND_IMAGE" >> "$TRACE"
case "$*" in
  "inspect schoolwall-cn-backend-1 --format {{{{.Config.Image}}}}") echo '{OLD_IMAGE}' ;;
  "exec schoolwall-cn-backend-1 python"*) echo '{OLD_REVISION}' ;;
  "inspect -f {{{{.State.Health.Status}}}} backend-id") echo healthy ;;
  "exec backend-id python"*) echo "$FAKE_REVISION" ;;
  *"ps -q backend"*) echo backend-id ;;
  *"ps --status running -q worker"*) echo worker-id ;;
  *"run --rm migrate"*) [ "$FAIL_MIGRATION" != 1 ] || exit 17 ;;
esac
""")
        (binary / "docker").chmod(0o700)
        env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"],
                   TRACE=str(trace), FAKE_REVISION=REVISION, FAIL_MIGRATION="0")
        return target, source, env, trace

    def test_cn_release_updates_only_packaged_web_and_preserves_pc(self):
        target, source, env, trace = self.prepare()
        result = subprocess.run(["bash", str(ROOT / "scripts/rollout-cn.sh"), str(target), str(source)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((target / "web/h5/index.html").read_text(), "new h5")
        self.assertEqual((target / "web/admin/index.html").read_text(), "new admin")
        self.assertEqual((target / "web/pc/index.html").read_text(), "old pc")
        self.assertEqual((target / ("web/h5.before-" + REVISION) / "index.html").read_text(), "old h5")
        self.assertEqual((target / "current").resolve(), target / "releases" / REVISION)
        self.assertEqual(trace.read_text().count("run --rm migrate"), 1)
        retry = subprocess.run(["bash", str(ROOT / "scripts/rollout-cn.sh"), str(target), str(source)],
                               env=env, capture_output=True, text=True)
        self.assertEqual(retry.returncode, 0, retry.stderr)
        self.assertEqual((target / "web/pc/index.html").read_text(), "old pc")
        self.assertEqual(trace.read_text().count("run --rm migrate"), 2)

    def test_failed_migration_restores_previous_application(self):
        target, source, env, trace = self.prepare()
        env["FAIL_MIGRATION"] = "1"
        result = subprocess.run(["bash", str(ROOT / "scripts/rollout-cn.sh"), str(target), str(source)],
                                env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        commands = trace.read_text().splitlines()
        self.assertIn(OLD_IMAGE, commands[-1])
        self.assertIn("up -d --no-build backend worker", commands[-1])
        self.assertEqual((target / "web/h5/index.html").read_text(), "old h5")
        self.assertNotIn("downgrade", trace.read_text())


if __name__ == "__main__":
    unittest.main()
