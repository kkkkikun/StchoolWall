"""Exercise the production cutover with synthetic legacy data in an EMPTY isolated database.
This command deliberately migrates/downgrades only its explicitly named test database.
"""
import asyncio
import copy
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


# 旧版夹具：插在链底 61edfd32690b 的 schema 上，只有假数据（没有真实姓名与学号）。
LEGACY_BASE_REVISION = "61edfd32690b"
LEGACY_TABLES = ("users", "posts", "tags", "post_tags", "reports")
DEV_DEMO_OPENIDS = ("dev_demo_admin", "dev_demo_student")
# 举报行被「不在 users 里的 console 管理员」处理过的旧版状态（d4e5f6a7b910 回滚时会被清理）。
CONSOLE_ADMIN_ID = "00000000-0000-4000-8000-000000000001"

LegacyUser = namedtuple("LegacyUser", "openid role is_verified status student_id real_name nickname")
LEGACY_USERS = (
    LegacyUser("dev_demo_student", "student", True, 1,
               "synthetic-student-4", "synthetic-name-4", "synthetic bottom fixture"),
    LegacyUser("legacy_bottom_wx_openid", "student", True, 1,
               "synthetic-student-2", "synthetic-name-2", "synthetic bottom fixture"),
    LegacyUser("mp:legacy_bottom_mp_openid", "student", True, 1,
               "synthetic-student-3", "synthetic-name-3", "synthetic bottom fixture"),
    LegacyUser("web:legacy_bottom_fixture", "student", True, 1,
               "synthetic-student-1", "synthetic-name-1", "synthetic bottom fixture"),
)
LEGACY_TAGS = ("synthetic-bottom-tag-a", "synthetic-bottom-tag-b")
# 帖子：post_type / content / status
LEGACY_POST = ("general", "synthetic bottom fixture", 1)
# 举报：reason / description / status
LEGACY_REPORT = ("synthetic bottom reason", "synthetic bottom description", "pending")
# 夹具只写链底已有的列（id 自增的表不写 id）。
LEGACY_USER_COLUMNS = ("id", "openid", "nickname", "role", "is_verified",
                        "status", "student_id", "real_name")
LEGACY_POST_COLUMNS = ("user_id", "post_type", "content", "images", "status")
LEGACY_TAG_COLUMNS = ("name",)
LEGACY_POST_TAG_COLUMNS = ("post_id", "tag_id")
LEGACY_REPORT_COLUMNS = ("post_id", "reporter_id", "reason", "description", "status")


def cutover_effect(expected):
    """529bf8becb3f 自己声明的语义变化：旧认证与原始姓名/学号被清理。"""
    updated = copy.deepcopy(expected)
    for row in updated["users"]:
        row["is_verified"] = False
        row["student_id"] = None
        row["real_name"] = None
        if row["role"] in ("student", "admin"):
            row["role"] = "guest"
        if row["openid"] in DEV_DEMO_OPENIDS:
            row["status"] = -2
    return updated


def report_cleanup_effect(expected):
    """d4e5f6a7b910 自己声明的语义变化：回滚前清理 handled_by 不在 users 里的举报行。"""
    updated = copy.deepcopy(expected)
    updated["reports"] = []
    return updated


# 「只允许声明过的语义变化」白名单：key = (迁移 revision, 方向)，value = (说明, 期望状态推进函数)。
# 断言逻辑：每一步的期望状态只按白名单里声明过的变化推进；白名单之外的任何行数或字段变化都断言失败。
SEMANTIC_CHANGES = {
    ("529bf8becb3f", "upgrade"): (
        "旧认证与原始姓名/学号被清理：is_verified=false、student_id/real_name=NULL、"
        "role 降为 guest、dev 演示账号 status=-2",
        cutover_effect),
    ("d4e5f6a7b910", "downgrade"): (
        "回滚前清理 handled_by 不在 users 里的举报行",
        report_cleanup_effect),
}

# 旧版真实状态调整：在列存在且外键已解除后写入「举报行由不在 users 里的 console 管理员处理」，
# 以真实触发 d4e5f6a7b910 回滚时那条举报行被清理（它自己声明的语义变化）。
LEGACY_STATE_ADJUSTMENTS = {("d4e5f6a7b910", "upgrade"): "report_handled_by_console_admin"}


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


async def insert_legacy_fixture(url):
    """在链底插入合成的旧版夹具（用户 / 帖子 / 标签 / 帖子标签 / 举报），只有假数据。"""
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        users = {}
        for spec in LEGACY_USERS:
            users[spec.openid] = await connection.fetchval(
                f"INSERT INTO users ({', '.join(LEGACY_USER_COLUMNS)})"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id",
                uuid.uuid4(), spec.openid, spec.nickname, spec.role,
                spec.is_verified, spec.status, spec.student_id, spec.real_name)
        tags = {}
        for name in LEGACY_TAGS:
            tags[name] = await connection.fetchval(
                f"INSERT INTO tags ({', '.join(LEGACY_TAG_COLUMNS)}) VALUES ($1) RETURNING id",
                name)
        post_id = await connection.fetchval(
            f"INSERT INTO posts ({', '.join(LEGACY_POST_COLUMNS)})"
            " VALUES ($1,$2,$3,'[]'::jsonb,$4) RETURNING id",
            users[LEGACY_USERS[0].openid], LEGACY_POST[0], LEGACY_POST[1], LEGACY_POST[2])
        await connection.execute(
            f"INSERT INTO post_tags ({', '.join(LEGACY_POST_TAG_COLUMNS)}) VALUES ($1,$2)",
            post_id, tags[LEGACY_TAGS[0]])
        report_id = await connection.fetchval(
            f"INSERT INTO reports ({', '.join(LEGACY_REPORT_COLUMNS)})"
            " VALUES ($1,$2,$3,$4,$5) RETURNING id",
            post_id, users[LEGACY_USERS[0].openid],
            LEGACY_REPORT[0], LEGACY_REPORT[1], LEGACY_REPORT[2])
        return {"post_user_id": users[LEGACY_USERS[0].openid], "post_id": post_id,
                "tag_id": tags[LEGACY_TAGS[0]], "reporter_id": users[LEGACY_USERS[0].openid],
                "report_id": report_id}
    finally:
        await connection.close()


def legacy_expectation(fixtures):
    """链底夹具的期望状态：旧数据原样存在（行数与关键字段）。"""
    return {
        "users": [
            {"openid": spec.openid, "nickname": spec.nickname, "role": spec.role,
             "is_verified": spec.is_verified, "status": spec.status,
             "student_id": spec.student_id, "real_name": spec.real_name}
            for spec in sorted(LEGACY_USERS, key=lambda item: item.openid)],
        "posts": [{"user_id": fixtures["post_user_id"], "post_type": LEGACY_POST[0],
                   "content": LEGACY_POST[1], "status": LEGACY_POST[2]}],
        "tags": [{"name": name} for name in sorted(LEGACY_TAGS)],
        "post_tags": [{"post_id": fixtures["post_id"], "tag_id": fixtures["tag_id"]}],
        "reports": [{"post_id": fixtures["post_id"], "reporter_id": fixtures["reporter_id"],
                     "reason": LEGACY_REPORT[0], "description": LEGACY_REPORT[1],
                     "status": LEGACY_REPORT[2]}],
    }


async def fetch_legacy_state(url):
    """旧版夹具涉及的五张表在当前 schema 下的实际内容（只取关键字段）。"""
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        return {
            "users": [dict(row) for row in await connection.fetch(
                "SELECT openid, nickname, role, is_verified, status, student_id, real_name"
                " FROM users ORDER BY openid")],
            "posts": [dict(row) for row in await connection.fetch(
                "SELECT user_id, post_type, content, status FROM posts ORDER BY id")],
            "tags": [dict(row) for row in await connection.fetch(
                "SELECT name FROM tags ORDER BY name")],
            "post_tags": [dict(row) for row in await connection.fetch(
                "SELECT post_id, tag_id FROM post_tags ORDER BY post_id, tag_id")],
            "reports": [dict(row) for row in await connection.fetch(
                "SELECT post_id, reporter_id, reason, description, status"
                " FROM reports ORDER BY id")],
        }
    finally:
        await connection.close()


def legacy_difference(expected, actual):
    """两份旧数据期望与实际的差异摘要（逐行比较）。"""
    differences = []
    for index, (left, right) in enumerate(zip(expected, actual)):
        if left != right:
            differences.append(f"row {index}: expected {left}, got {right}")
    if len(expected) != len(actual):
        differences.append(f"row count: expected {len(expected)}, got {len(actual)}")
    return "; ".join(differences[:5]) or "no difference"


async def assert_legacy_data(url, expected, step, direction):
    """逐条断言旧数据：行数与关键字段必须与期望一致。

    期望状态只按白名单里声明过的语义变化推进，因此任何未声明的行数或字段变化都会失败。
    """
    actual = await fetch_legacy_state(url)
    for table in LEGACY_TABLES:
        assert actual[table] == expected[table], (
            f"legacy {table} data must stay unchanged after "
            f"{'upgrading' if direction == 'upgrade' else 'downgrading'} {step.revision} "
            f"except for the declared semantic changes: "
            + legacy_difference(expected[table], actual[table]))


def apply_semantic_change(expected, step, direction):
    """按白名单里声明过的语义变化推进期望状态；未声明的变化一律不允许。"""
    change = SEMANTIC_CHANGES.get((step.revision, direction))
    return expected if change is None else change[1](expected)


async def apply_legacy_state_adjustment(url, fixtures, step, direction):
    """在允许的时机写入旧版真实状态（此处：举报行由不在 users 里的 console 管理员处理）。"""
    if LEGACY_STATE_ADJUSTMENTS.get((step.revision, direction)) != "report_handled_by_console_admin":
        return
    import asyncpg
    connection = await asyncpg.connect(url)
    try:
        await connection.execute("UPDATE reports SET handled_by = $1 WHERE id = $2",
                                 uuid.UUID(CONSOLE_ADMIN_ID), fixtures["report_id"])
    finally:
        await connection.close()


async def assert_legacy_data_survives_chain(url, chain=CHAIN):
    """链底旧版夹具 → 整链升级到 head → 整链回退到链底，逐条断言旧数据不丢。

    在链底插入合成的旧版夹具后，每条迁移执行完都断言旧数据的行数与关键字段依然成立；
    只有迁移自己声明过的语义变化（切换迁移 529bf8becb3f 的旧认证与原始姓名/学号清理、
    d4e5f6a7b910 回滚时的举报行清理）才允许出现。最后退回空库，供既有夹具流程继续。
    """
    migrate("upgrade", chain[0].revision)
    fixtures = await insert_legacy_fixture(url)
    expected = legacy_expectation(fixtures)
    await assert_legacy_data(url, expected, chain[0], "upgrade")
    for step in chain[1:]:
        migrate("upgrade", step.revision)
        expected = apply_semantic_change(expected, step, "upgrade")
        await apply_legacy_state_adjustment(url, fixtures, step, "upgrade")
        await assert_legacy_data(url, expected, step, "upgrade")
    for step in reversed(chain[1:]):
        migrate("downgrade", step.parent)
        expected = apply_semantic_change(expected, step, "downgrade")
        await assert_legacy_data(url, expected, step, "downgrade")
    migrate("downgrade", BASE_TARGET)
    print(f"legacy fixture rows and key fields preserved across all {len(chain)} revisions"
          f" of the chain: PASS")


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
    # 链底旧版夹具 → 整链升级 → 整链回退：逐条断言旧数据不丢
    asyncio.run(assert_legacy_data_survives_chain(url))
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
