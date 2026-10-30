"""Logical backup/restore smoke for synthetic migration fixtures, never production data."""
import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

TABLES = ("users", "login_identities", "posts", "footprints", "jobs", "student_verifications")


def guarded_urls():
    url = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://", 1)
    parts = urlparse(url)
    source = parts.path.lstrip("/")
    if (os.environ.get("ENVIRONMENT") != "test"
            or os.environ.get("MIGRATION_TEST_ACK") != "YES_ISOLATED_DATABASE"
            or not re.fullmatch(r"[a-z][a-z0-9_]*", source)
            or not source.endswith(("_migration", "_migration_test"))):
        raise SystemExit("Restore smoke requires an isolated synthetic migration database and explicit ACK")
    target = source + "_restore_test"
    return url, urlunparse(parts._replace(path="/" + target)), source, target


async def prepare(source_url, target):
    import asyncpg
    conn = await asyncpg.connect(source_url)
    try:
        if not await conn.fetchval("SELECT count(*) FROM users"):
            raise SystemExit("Source must contain synthetic migration fixtures")
        if await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", target):
            raise SystemExit("Restore target already exists; existing databases are never erased")
        await conn.execute('CREATE DATABASE "' + target + '"')
    finally:
        await conn.close()


def tools(source_url, target_url, source, target):
    container = os.environ.get("POSTGRES_TEST_CONTAINER")
    if container:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", container):
            raise SystemExit("Invalid test container ID")
        prefix = ["docker", "exec", "-i", "-e", "PGPASSWORD", container]
        return (prefix + ["pg_dump", "--username=postgres", "--dbname=" + source, "--format=custom"],
                prefix + ["pg_restore", "--username=postgres", "--dbname=" + target,
                          "--exit-on-error", "--no-owner", "--no-acl"], os.environ.copy())
    directory = os.environ.get("PG_BIN_DIR", "")
    dump = str(Path(directory) / "pg_dump") if directory else shutil.which("pg_dump")
    restore = str(Path(directory) / "pg_restore") if directory else shutil.which("pg_restore")
    if not dump or not restore:
        raise SystemExit("Set PG_BIN_DIR to matching PostgreSQL client binaries")
    parsed = urlparse(source_url)
    env = dict(os.environ, PGHOST=parsed.hostname or "", PGPORT=str(parsed.port or 5432),
               PGUSER=parsed.username or "", PGPASSWORD=parsed.password or "")
    return ([dump, "--dbname=" + source, "--format=custom"],
            [restore, "--dbname=" + target, "--exit-on-error", "--no-owner", "--no-acl"], env)


async def compare(source_url, target_url):
    import asyncpg
    left, right = await asyncpg.connect(source_url), await asyncpg.connect(target_url)
    try:
        counts = {}
        for table in TABLES:
            query = "SELECT count(*) FROM " + table
            before, after = await left.fetchval(query), await right.fetchval(query)
            assert before == after, (table, before, after)
            counts[table] = after
        query = "SELECT id,openid,web_password_hash,is_verified,student_id,real_name FROM users ORDER BY id"
        assert await left.fetch(query) == await right.fetch(query)
        query = "SELECT * FROM login_identities ORDER BY id"
        assert await left.fetch(query) == await right.fetch(query)
        query = "SELECT version_num FROM alembic_version"
        assert await left.fetchval(query) == await right.fetchval(query)
        print("Synthetic logical restore matched rows, identities and schema version:", counts)
    finally:
        await left.close()
        await right.close()


if __name__ == "__main__":
    source_url, target_url, source, target = guarded_urls()
    dump_command, restore_command, env = tools(source_url, target_url, source, target)
    asyncio.run(prepare(source_url, target))
    with tempfile.TemporaryDirectory(prefix="schoolwall-restore-smoke-") as td:
        archive = Path(td) / "synthetic.dump"
        with archive.open("wb") as output:
            subprocess.run(dump_command, env=env, stdout=output, check=True)
        if not archive.stat().st_size:
            raise SystemExit("Empty logical backup")
        with archive.open("rb") as data:
            subprocess.run(restore_command, env=env, stdin=data, check=True)
    asyncio.run(compare(source_url, target_url))
    print("Logical restore smoke PASS; this is not off-host PITR/RPO/RTO evidence")
