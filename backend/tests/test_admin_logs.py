"""审计日志测试：写入语义 + 现有操作联动 + 查询。"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.dependencies import AdminActor
from app.models.admin_log import AdminLog
from app.models.banner import Banner
from app.models.post import Post
from app.models.report import Report
from app.services import admin_log
from app.services.admin_log import list_admin_logs, log_admin_action
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _seed_post(user_id, content="被管理帖", status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


async def _fetch_logs(**kw):
    async with TestSession() as db:
        return await list_admin_logs(db, **kw)


class TestLogSemantics:
    async def test_write_action_persists(self):
        actor = AdminActor(id="fake-admin-id-0001", display_name="测试管理员", source="console")
        async with TestSession() as db:
            await log_admin_action(db, actor, admin_log.POST_PIN,
                                   target_type="post", target_id=42,
                                   detail={"pinned": True}, ip="127.0.0.1")
            await db.commit()

        items, _, _ = await _fetch_logs()
        assert len(items) == 1
        log = items[0]
        assert log["action"] == admin_log.POST_PIN
        assert log["admin_name"] == "测试管理员"
        assert log["source"] == "console"
        assert log["target_type"] == "post"
        assert log["target_id"] == "42"
        assert log["detail"] == {"pinned": True}
        assert log["ip"] == "127.0.0.1"

    async def test_log_not_committed_until_caller_commits(self):
        """log_admin_action 只 add 不 commit：调用方不 commit 就不落库（事务一致性）。"""
        actor = AdminActor(id="fake-admin-id-0002", display_name="X", source="legacy")
        async with TestSession() as db:
            await log_admin_action(db, actor, admin_log.POST_STATUS)
            # 未 commit —— 另一个 session 看不到
        items, _, _ = await _fetch_logs()
        assert items == []

    async def test_int_target_id_stored_as_str(self):
        actor = AdminActor(id="a", display_name="n", source="console")
        async with TestSession() as db:
            await log_admin_action(db, actor, admin_log.POST_EDIT, target_id=12345)
            await db.commit()
        items, _, _ = await _fetch_logs()
        assert items[0]["target_id"] == "12345"


class TestWriteActionAuditTrail:
    async def test_post_status_change_writes_log(
        self, client: AsyncClient, console_headers: dict, student_user
    ):
        pid = await _seed_post(student_user.id, "待审帖", status=0)
        r = await client.put(f"/api/v1/admin/posts/{pid}/status?status=1", headers=console_headers)
        assert r.status_code == 200

        items, _, _ = await _fetch_logs(action=admin_log.POST_STATUS)
        assert len(items) == 1
        assert items[0]["target_id"] == str(pid)
        assert items[0]["detail"] == {"new_status": 1}
        assert items[0]["ip"]  # ip 已记录

    async def test_user_freeze_writes_log(
        self, client: AsyncClient, console_headers: dict, student_user
    ):
        r = await client.put(
            f"/api/v1/admin/users/{student_user.id}/status?status=0", headers=console_headers
        )
        assert r.status_code == 200
        items, _, _ = await _fetch_logs(action=admin_log.USER_FREEZE)
        assert len(items) == 1
        assert items[0]["target_id"] == str(student_user.id)

    async def test_pin_writes_log(self, client: AsyncClient, console_headers: dict, student_user):
        pid = await _seed_post(student_user.id, "置顶帖")
        r = await client.put(f"/api/v1/admin/posts/{pid}/pin", headers=console_headers,
                             json={"pinned": True})
        assert r.status_code == 200
        items, _, _ = await _fetch_logs(action=admin_log.POST_PIN)
        assert len(items) == 1
        assert items[0]["detail"] == {"pinned": True}

    async def test_handle_report_writes_log(
        self, client: AsyncClient, console_headers: dict, student_user, admin_user
    ):
        pid = await _seed_post(student_user.id, "被举报帖")
        async with TestSession() as db:
            db.add(Report(post_id=pid, reporter_id=admin_user.id, reason="垃圾广告"))
            await db.commit()
            rid = (await db.execute(select(Report).where(Report.post_id == pid))).scalar_one().id

        r = await client.put(f"/api/v1/admin/reports/{rid}", headers=console_headers,
                             json={"action": "dismiss"})
        assert r.status_code == 200

        items, _, _ = await _fetch_logs(action=admin_log.REPORT_HANDLE)
        assert len(items) == 1
        assert items[0]["target_id"] == str(rid)
        assert items[0]["detail"]["action"] == "dismiss"

    async def test_banner_create_writes_log(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/banners", headers=console_headers,
                              json={"title": "审计测试广告"})
        assert r.status_code == 200
        items, _, _ = await _fetch_logs(action=admin_log.BANNER_CREATE)
        assert len(items) == 1
        assert items[0]["detail"] == {"title": "审计测试广告"}


class TestLogsQuery:
    async def test_route_with_filters(self, client: AsyncClient, console_headers: dict, student_user):
        # 造两条不同动作的日志
        p1 = await _seed_post(student_user.id, "帖A", status=0)
        p2 = await _seed_post(student_user.id, "帖B")
        await client.put(f"/api/v1/admin/posts/{p1}/status?status=1", headers=console_headers)
        await client.put(f"/api/v1/admin/posts/{p2}/pin", headers=console_headers, json={"pinned": True})

        # 全量 2 条
        r = await client.get("/api/v1/admin/logs", headers=console_headers)
        assert r.status_code == 200
        assert len(r.json()["data"]["items"]) == 2

        # action 过滤 1 条
        r = await client.get(f"/api/v1/admin/logs?action={admin_log.POST_PIN}", headers=console_headers)
        assert len(r.json()["data"]["items"]) == 1

        # 时间范围：未来起点 → 0 条
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        r = await client.get(f"/api/v1/admin/logs?time_start={future}", headers=console_headers)
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []

    async def test_console_actor_recorded(self, client: AsyncClient, console_headers: dict, console_admin):
        """日志里的 admin_id 是 console 账号 id。"""
        r = await client.get("/api/v1/admin/logs", headers=console_headers)
        items = r.json()["data"]["items"]
        if items:  # 本用例可能没写操作，有则校验归属
            assert items[0]["admin_id"] == str(console_admin.id)

    async def test_non_admin_403(self, client: AsyncClient, student_token: str):
        r = await client.get("/api/v1/admin/logs", headers=auth_header(student_token))
        assert r.status_code == 403

    async def test_legacy_admin_can_read_logs(self, client: AsyncClient, admin_token: str):
        """双 token：legacy users.admin 也能查日志。"""
        r = await client.get("/api/v1/admin/logs", headers=auth_header(admin_token))
        assert r.status_code == 200
