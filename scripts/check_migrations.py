"""Exercise the production cutover with synthetic legacy data in an EMPTY isolated database.
This command deliberately migrates/downgrades only its explicitly named test database.
"""
import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = "a7b8c9d0e1f2"
CUTOVER_REVISION = "529bf8becb3f"


def guard() -> str:
    url = os.environ.get("DATABASE_URL", "")
    database = urlparse(url).path.lstrip("/")
    if (os.environ.get("ENVIRONMENT") != "test"
            or os.environ.get("MIGRATION_TEST_ACK") != "YES_ISOLATED_DATABASE"
            or not database.endswith(("_migration", "_migration_test"))):
        raise SystemExit("Requires test environment, explicit ACK and *_migration[_test] empty database")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def ensure_empty(url):
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        exists = await connection.fetchval("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public')")
        if exists:
            raise SystemExit("Migration test database must be empty; existing data is never erased")
    finally:
        await connection.close()


def migrate(*arguments):
    subprocess.run([sys.executable, "-m", "alembic", *arguments], cwd=ROOT / "backend", check=True)


async def legacy_fixtures(url):
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        ids = [uuid.uuid4() for _ in range(4)]
        password_hash = "$2b$12$synthetic.migration.fixture.hash.never.for.real.login"
        for uid, openid, role in zip(ids,
                ("web:legacy_fixture", "legacy_wx_openid", "mp:legacy_mp_openid", "dev_demo_student"),
                ("student", "student", "student", "student")):
            await connection.execute("""INSERT INTO users
                (id,openid,nickname,role,is_verified,status,student_id,real_name,web_password_hash)
                VALUES($1,$2,'synthetic migration fixture',$3,true,1,$4,'synthetic-name',$5)""",
                uid, openid, role, "synthetic-" + uid.hex[:6], password_hash)
        post_id = await connection.fetchval("""INSERT INTO posts
            (user_id,post_type,content,images,status,is_pinned,is_featured,like_count,comment_count,view_count)
            VALUES($1,'general','synthetic migration fixture','[]'::jsonb,1,false,false,0,0,0) RETURNING id""", ids[0])
        await connection.execute("""INSERT INTO footprints(user_id,post_id,viewed_at)
            VALUES($1,$2,now()-interval '1 day')""", ids[0], post_id)
        latest = await connection.fetchval("""INSERT INTO footprints(user_id,post_id,viewed_at)
            VALUES($1,$2,now()) RETURNING id""", ids[0], post_id)
        return ids, password_hash, post_id, latest
    finally:
        await connection.close()


async def verify(url, fixtures):
    import asyncpg
    connection = await asyncpg.connect(url)
    ids, password_hash, post_id, latest = fixtures
    try:
        web = await connection.fetchrow("SELECT * FROM users WHERE id=$1", ids[0])
        assert web["web_password_hash"] == password_hash
        for uid in ids:
            user = await connection.fetchrow("SELECT * FROM users WHERE id=$1", uid)
            assert user and user["id"] == uid
            assert user["is_verified"] is False and user["verified_until"] is None
            assert user["real_name"] is None and user["student_id"] is None
            assert user["role"] == "guest"
        assert await connection.fetchval("SELECT status FROM users WHERE id=$1", ids[3]) == -2
        identity = await connection.fetchrow("SELECT * FROM login_identities WHERE user_id=$1", ids[0])
        assert identity["provider"] == "password" and identity["subject"] == "legacy_fixture"
        assert identity["password_hash"] == password_hash
        for uid, provider, subject in (
            (ids[1], "weixin:migration-test-app", "legacy_wx_openid"),
            (ids[2], "mp:migration-mp-test-app", "legacy_mp_openid"),
        ):
            row = await connection.fetchrow("SELECT * FROM login_identities WHERE user_id=$1", uid)
            assert row and row["provider"] == provider and row["subject"] == subject
        footprints = await connection.fetch("SELECT id FROM footprints WHERE user_id=$1 AND post_id=$2", ids[0], post_id)
        assert len(footprints) == 1 and footprints[0]["id"] == latest
        print("legacy UUID/password identities preserved; old verification/PII invalidated; newest footprint retained")
    finally:
        await connection.close()


if __name__ == "__main__":
    url = guard()
    asyncio.run(ensure_empty(url))
    os.environ["WECHAT_APP_ID"] = "migration-test-app"
    os.environ["WECHAT_MP_APP_ID"] = "migration-mp-test-app"
    migrate("upgrade", BASE_REVISION)
    fixtures = asyncio.run(legacy_fixtures(url))
    migrate("upgrade", "head")
    asyncio.run(verify(url, fixtures))
    migrate("downgrade", "-1")
    migrate("upgrade", "head")
    asyncio.run(verify(url, fixtures))
    migrate("check")
    print("Migration cutover, rollback/re-upgrade and metadata consistency: PASS")
