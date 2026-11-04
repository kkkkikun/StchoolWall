"""Exercise the production cutover with synthetic legacy data in an EMPTY isolated database.
This command deliberately migrates/downgrades only its explicitly named test database.
"""
import asyncio
import os
import subprocess
import sys
import uuid
from collections import namedtuple
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = "a7b8c9d0e1f2"
CUTOVER_REVISION = "529bf8becb3f"
POSITION_REVISION = "b7e2c4a91d30"
POSITION_TABLE = "media_assets"
POSITION_COLUMN = "position"
BASE_TARGET = "base"

# 迁移链：每条迁移的父版本，以及它「引入」和「移除」的对象。
# 探针四类：("table", 表名) / ("column", 表名, 列名) / ("index", 索引名) / ("constraint", 表名, 约束名)。
# 「引入」= upgrade 后存在、downgrade 后消失；「移除」= upgrade 后消失、downgrade 后恢复。
# 链上每条迁移都要能被单独回退再恢复，因此这份清单必须与迁移文件逐条对得上。
Step = namedtuple("Step", "revision parent introduced removed")
CHAIN = (
    Step("61edfd32690b", None,
         (("table", "tags"), ("table", "users"), ("table", "posts"),
          ("table", "post_tags"), ("table", "reports")),
         ()),
    Step("a8f3c2e1b904", "61edfd32690b",
         (("table", "comments"), ("table", "likes"), ("table", "favorites"),
          ("table", "footprints"), ("column", "posts", "like_count"),
          ("column", "posts", "comment_count"), ("column", "posts", "view_count")),
         ()),
    Step("c2b4f6a8d910", "a8f3c2e1b904",
         (("table", "notifications"),),
         ()),
    Step("d5c7e9f1a203", "c2b4f6a8d910",
         (("table", "parties"), ("table", "party_members")),
         ()),
    Step("e6f8a1b3c405", "d5c7e9f1a203",
         (("column", "posts", "category"), ("index", "ix_posts_category")),
         ()),
    Step("f7a9c2d4e506", "e6f8a1b3c405",
         (("table", "user_follows"), ("index", "ix_user_follows_followee")),
         ()),
    Step("a1b2c3d4e607", "f7a9c2d4e506",
         (("table", "banners"), ("column", "posts", "is_pinned"),
          ("column", "posts", "pinned_at"), ("column", "reports", "handled_by"),
          ("column", "reports", "handled_at"), ("index", "ix_posts_is_pinned")),
         ()),
    Step("b2c3d4e5f708", "a1b2c3d4e607",
         (("table", "admin_users"), ("index", "ix_admin_users_username")),
         ()),
    Step("c3d4e5f6a809", "b2c3d4e5f708",
         (("table", "admin_logs"),),
         ()),
    Step("d4e5f6a7b910", "c3d4e5f6a809",
         (),
         (("constraint", "reports", "fk_reports_handled_by_users"),)),
    Step("e5f6a7b8c011", "d4e5f6a7b910",
         (("column", "notifications", "payload"), ("column", "notifications", "batch_id"),
          ("index", "ix_notifications_batch_id")),
         ()),
    Step("8dd9dd74cb0a", "e5f6a7b8c011",
         (("column", "posts", "is_featured"), ("column", "posts", "featured_at"),
          ("index", "ix_posts_is_featured")),
         ()),
    Step("360667a805e8", "8dd9dd74cb0a",
         (("table", "check_ins"), ("index", "ix_check_ins_user_id")),
         ()),
    Step("c46310ba7252", "360667a805e8",
         (("column", "users", "banner_url"),),
         ()),
    Step("3fa1e19abdf2", "c46310ba7252",
         (("column", "users", "bio"),),
         ()),
    Step("e8b1c4f7a2d9", "3fa1e19abdf2",
         (("table", "sensitive_words"), ("table", "moderation_records")),
         ()),
    Step("f2a8d5c1e3b7", "e8b1c4f7a2d9",
         (("column", "users", "web_password_hash"),),
         ()),
    Step("b4d7e2f9a1c5", "f2a8d5c1e3b7",
         (("column", "moderation_records", "comment_id"),
          ("index", "ix_moderation_records_comment_id")),
         ()),
    Step("a7b8c9d0e1f2", "b4d7e2f9a1c5",
         (("table", "activities"), ("column", "banners", "activity_id"),
          ("index", "ix_activities_status")),
         ()),
    Step("529bf8becb3f", "a7b8c9d0e1f2",
         (("table", "jobs"), ("table", "appeals"), ("table", "login_identities"),
          ("table", "media_assets"), ("table", "pairing_codes"), ("table", "recovery_codes"),
          ("table", "student_identity_claims"), ("table", "student_verification_challenges"),
          ("table", "user_blocks"), ("table", "student_verifications"),
          ("table", "user_sessions"), ("table", "spent_refresh_tokens"),
          ("column", "users", "verified_until"),
          ("column", "admin_users", "mfa_secret_encrypted"),
          ("column", "admin_users", "mfa_last_counter")),
         (("constraint", "admin_users", "admin_users_username_key"),
          ("constraint", "notifications", "notifications_post_id_fkey"))),
    Step("b7e2c4a91d30", "529bf8becb3f",
         (("column", "media_assets", "position"),),
         ()),
    Step("d4e6f8a1b357", "b7e2c4a91d30",
         (("table", "feedbacks"),),
         ()),
    Step("c1d2e3f4a5b6", "d4e6f8a1b357",
         (("table", "post_view_counters"),),
         ()),
    Step("d7e8f9a0b123", "c1d2e3f4a5b6",
         (("table", "post_hot_scores"), ("table", "post_hot_score_state"),
          ("index", "ix_posts_content_trgm"), ("index", "ix_posts_featured_id")),
         ()),
)


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


async def applied_revision(url):
    """当前 alembic_version；回退到 base 时版本表可能已空或不存在，此时返回 None。"""
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        if not await connection.fetchval("SELECT to_regclass('public.alembic_version')"):
            return None
        return await connection.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await connection.close()


async def column_present(url, table, column):
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        return bool(await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns"
            " WHERE table_schema='public' AND table_name=$1 AND column_name=$2)",
            table, column))
    finally:
        await connection.close()


async def table_present(url, table):
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        return bool(await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables"
            " WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name=$1)",
            table))
    finally:
        await connection.close()


async def index_present(url, index):
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        return bool(await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_indexes"
            " WHERE schemaname='public' AND indexname=$1)",
            index))
    finally:
        await connection.close()


async def constraint_present(url, table, constraint):
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        return bool(await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.table_constraints"
            " WHERE table_schema='public' AND table_name=$1 AND constraint_name=$2)",
            table, constraint))
    finally:
        await connection.close()


async def schema_snapshot(url):
    """整库 schema 快照（表/列/索引/约束），用于比对往返前后是否逐字一致。"""
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        tables = await connection.fetch(
            "SELECT table_name FROM information_schema.tables"
            " WHERE table_schema='public' AND table_type='BASE TABLE'"
            " AND table_name <> 'alembic_version' ORDER BY table_name")
        columns = await connection.fetch(
            "SELECT table_name, column_name, udt_name, is_nullable,"
            " character_maximum_length, column_default FROM information_schema.columns"
            " WHERE table_schema='public' AND table_name <> 'alembic_version'"
            " ORDER BY table_name, column_name")
        indexes = await connection.fetch(
            "SELECT indexname, tablename, indexdef FROM pg_indexes"
            " WHERE schemaname='public' AND tablename <> 'alembic_version'"
            " ORDER BY indexname")
        constraints = await connection.fetch(
            "SELECT table_name, constraint_name, constraint_type"
            " FROM information_schema.table_constraints"
            " WHERE table_schema='public' AND table_name <> 'alembic_version'"
            # PostgreSQL 15 把 NOT NULL 也记成内部 CHECK 约束，名字里带 OID
            # （形如 2200_31634_1_not_null），跨库必然不同，不是 schema 语义。
            " AND constraint_name !~ '^[0-9_]+_not_null$'"
            " ORDER BY table_name, constraint_name")
        return (tuple(tuple(row) for row in tables),
                tuple(tuple(row) for row in columns),
                tuple(tuple(row) for row in indexes),
                tuple(tuple(row) for row in constraints))
    finally:
        await connection.close()


def describe(probe):
    kind = probe[0]
    if kind == "table":
        return f"table {probe[1]}"
    if kind == "column":
        return f"column {probe[1]}.{probe[2]}"
    if kind == "index":
        return f"index {probe[1]}"
    return f"constraint {probe[1]}.{probe[2]}"


def schema_difference(before, after):
    """两份 schema 快照的差异摘要（表/列/索引/约束逐项对比）。"""
    labels = ("tables", "columns", "indexes", "constraints")
    differences = []
    for label, left, right in zip(labels, before, after):
        missing = [item for item in left if item not in right]
        extra = [item for item in right if item not in left]
        for item in missing[:5]:
            differences.append(f"{label} missing: {item}")
        for item in extra[:5]:
            differences.append(f"{label} unexpected: {item}")
        if len(missing) > 5 or len(extra) > 5:
            differences.append(f"{label}: {len(missing)} missing / {len(extra)} unexpected")
    return "; ".join(differences)


async def probe_present(url, probe):
    kind = probe[0]
    if kind == "table":
        return await table_present(url, probe[1])
    if kind == "column":
        return await column_present(url, probe[1], probe[2])
    if kind == "index":
        return await index_present(url, probe[1])
    if kind == "constraint":
        return await constraint_present(url, probe[1], probe[2])
    raise AssertionError(f"unknown probe kind: {kind}")


async def assert_step_objects(url, step, applied):
    """applied=True：该迁移已生效，它引入的对象必须在、它移除的对象必须不在。

    applied=False：该迁移已回退，它引入的对象必须消失、它移除的对象必须恢复。
    """
    for probe in step.introduced:
        assert await probe_present(url, probe) is applied, (
            f"{describe(probe)} must be {'present' if applied else 'gone'} "
            f"after {'upgrading' if applied else 'downgrading'} {step.revision}")
    for probe in step.removed:
        assert await probe_present(url, probe) is not applied, (
            f"{describe(probe)} must be {'gone' if applied else 'restored'} "
            f"after {'upgrading' if applied else 'downgrading'} {step.revision}")


async def assert_chain_roundtrips(url, chain=CHAIN):
    """链上每条迁移逐条 downgrade/upgrade 往返断言。

    先整链升到 head 并记下 schema 快照，再从链尾逐条降级：每降一级就断言
    alembic_version 落到父版本、该迁移引入的对象确已消失、它移除的对象确已恢复，
    一直退到空库。然后从空库逐条升级回 head，每一级断言该迁移引入的对象确已恢复、
    它移除的对象确已消失，最后比对整库 schema 快照与往返前逐字一致。
    """
    migrate("upgrade", chain[0].revision)
    upgraded_base = await schema_snapshot(url)
    migrate("upgrade", "head")
    expected_head = await schema_snapshot(url)
    for step in reversed(chain[1:]):
        migrate("downgrade", step.parent)
        assert await applied_revision(url) == step.parent, (
            f"alembic_version must be back at {step.parent} after downgrading {step.revision}")
        await assert_step_objects(url, step, applied=False)
    migrate("downgrade", BASE_TARGET)
    assert await applied_revision(url) is None, (
        "alembic_version must be empty after downgrading the chain base")
    await assert_step_objects(url, chain[0], applied=False)
    for step in chain:
        migrate("upgrade", step.revision)
        assert await applied_revision(url) == step.revision, (
            f"alembic_version must be at {step.revision} after upgrading to it")
        await assert_step_objects(url, step, applied=True)
    restored = await schema_snapshot(url)
    assert restored == expected_head, (
        "the whole chain must come back to the very same schema after the round trip: "
        + schema_difference(expected_head, restored))
    migrate("downgrade", chain[0].revision)
    assert await applied_revision(url) == chain[0].revision, (
        f"alembic_version must be back at {chain[0].revision} after the round trip")
    base = await schema_snapshot(url)
    assert base == upgraded_base, (
        "the chain base must look the same whether it is upgraded to or downgraded to: "
        + schema_difference(upgraded_base, base))
    print(f"migration chain of {len(chain)} revisions downgraded and re-upgraded one by one "
          f"with an identical schema snapshot: PASS")


async def assert_position_rollback(url):
    """显式回滚迁移 b7e2c4a91d30，再恢复并逐项断言。

    `downgrade -1` 只回退链尾一条迁移，覆盖不到链中间的 b7e2c4a91d30，
    因此这里显式回退到它的父版本，断言 position 列真的被删掉、
    alembic_version 真的回到父版本，再 upgrade head 断言列真的恢复。
    """
    head = await applied_revision(url)
    assert head, "alembic_version must be set before the explicit rollback"
    assert await column_present(url, POSITION_TABLE, POSITION_COLUMN), \
        f"{POSITION_TABLE}.{POSITION_COLUMN} must exist before the explicit rollback"
    migrate("downgrade", CUTOVER_REVISION)
    assert await applied_revision(url) == CUTOVER_REVISION, \
        f"alembic_version must be back at {CUTOVER_REVISION} after the explicit downgrade"
    assert not await column_present(url, POSITION_TABLE, POSITION_COLUMN), \
        f"{POSITION_TABLE}.{POSITION_COLUMN} must be gone after downgrading to {CUTOVER_REVISION}"
    migrate("upgrade", "head")
    assert await applied_revision(url) == head, \
        "alembic_version must be back at head after re-upgrading"
    assert await column_present(url, POSITION_TABLE, POSITION_COLUMN), \
        f"{POSITION_TABLE}.{POSITION_COLUMN} must be restored after re-upgrading to head"
    print(f"migration {POSITION_REVISION} ({POSITION_TABLE}.{POSITION_COLUMN}) "
          f"downgrade to {CUTOVER_REVISION} and re-upgrade to head: PASS")


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
    # 链上每条迁移逐条 downgrade/upgrade 往返：先在空库上跑完，再进旧版夹具流程
    asyncio.run(assert_chain_roundtrips(url))
    migrate("upgrade", BASE_REVISION)
    fixtures = asyncio.run(legacy_fixtures(url))
    migrate("upgrade", "head")
    asyncio.run(verify(url, fixtures))
    migrate("downgrade", "-1")
    migrate("upgrade", "head")
    asyncio.run(verify(url, fixtures))
    asyncio.run(assert_position_rollback(url))
    asyncio.run(verify(url, fixtures))
    migrate("check")
    print("Migration cutover, rollback/re-upgrade and metadata consistency: PASS")
