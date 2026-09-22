"""批4：评论/组局/公告/趋势/导出测试。"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.interaction import Comment, Footprint
from app.models.party import Party
from app.models.post import Post
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _mk_post(user_id, content="评论宿主帖", status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


async def _mk_comment(user_id, post_id, content="一条评论") -> int:
    async with TestSession() as db:
        c = Comment(user_id=user_id, post_id=post_id, content=content)
        db.add(c)
        await db.commit()
        await db.refresh(c)
        return c.id


class TestComments:
    async def test_list_and_search(self, client, console_headers, student_user):
        pid = await _mk_post(student_user.id)
        await _mk_comment(student_user.id, pid, "正常评论")
        await _mk_comment(student_user.id, pid, "敏感词评论")

        r = await client.get("/api/v1/admin/comments?q=敏感词", headers=console_headers)
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["content"] == "敏感词评论"
        assert r.json()["data"]["total"] == 1

    async def test_filter_by_post(self, client, console_headers, student_user):
        p1 = await _mk_post(student_user.id, "帖1")
        p2 = await _mk_post(student_user.id, "帖2")
        await _mk_comment(student_user.id, p1)
        await _mk_comment(student_user.id, p2)
        r = await client.get(f"/api/v1/admin/comments?post_id={p1}", headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["post_id"] == p1

    async def test_soft_delete_comment_and_count_decrement(self, client, console_headers, student_user):
        pid = await _mk_post(student_user.id)
        cid = await _mk_comment(student_user.id, pid)
        # 帖子计数 +1
        async with TestSession() as db:
            from sqlalchemy import update
            await db.execute(update(Post).where(Post.id == pid).values(comment_count=1))
            await db.commit()

        r = await client.delete(f"/api/v1/admin/comments/{cid}", headers=console_headers)
        assert r.status_code == 200

        async with TestSession() as db:
            c = (await db.execute(select(Comment).where(Comment.id == cid))).scalar_one()
            assert c.status == -1  # 软删
            p = (await db.execute(select(Post).where(Post.id == pid))).scalar_one()
            assert p.comment_count == 0  # 计数同步

    async def test_delete_writes_audit(self, client, console_headers, student_user):
        from app.models.admin_log import AdminLog
        pid = await _mk_post(student_user.id)
        cid = await _mk_comment(student_user.id, pid)
        await client.delete(f"/api/v1/admin/comments/{cid}", headers=console_headers)
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "comment.delete"))).scalar_one()
            assert log.target_id == str(cid)

    async def test_delete_nonexistent_404(self, client, console_headers):
        r = await client.delete("/api/v1/admin/comments/999999", headers=console_headers)
        assert r.status_code == 404


class TestParties:
    async def _mk_party(self, user_id, title="周末爬山局", status=1) -> int:
        async with TestSession() as db:
            party = Party(user_id=user_id, type="group", category="兴趣社团",
                          title=title, content="组队爬山", total=5, status=status)
            db.add(party)
            await db.commit()
            await db.refresh(party)
            return party.id

    async def test_list_filter(self, client, console_headers, student_user):
        await self._mk_party(student_user.id, "搜我")
        await self._mk_party(student_user.id, "别的局", status=-1)
        r = await client.get("/api/v1/admin/parties?q=搜我", headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["title"] == "搜我"

    async def test_members_detail_and_404(self, client, console_headers, student_user):
        from app.models.party import PartyMember
        pid = await self._mk_party(student_user.id)
        async with TestSession() as db:
            db.add(PartyMember(party_id=pid, user_id=student_user.id))
            await db.commit()

        r = await client.get(f"/api/v1/admin/parties/{pid}/members", headers=console_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["nickname"] == student_user.nickname
        assert data["items"][0]["student_id"] == student_user.student_id

        r = await client.get("/api/v1/admin/parties/999999/members", headers=console_headers)
        assert r.status_code == 404

    async def test_close_and_restore(self, client, console_headers, student_user):
        pid = await self._mk_party(student_user.id)
        r = await client.put(f"/api/v1/admin/parties/{pid}/status?status=-1", headers=console_headers)
        assert r.status_code == 200
        r = await client.put(f"/api/v1/admin/parties/{pid}/status?status=1", headers=console_headers)
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 1

    async def test_invalid_status_400(self, client, console_headers, student_user):
        pid = await self._mk_party(student_user.id)
        # 1 → 1 非法
        r = await client.put(f"/api/v1/admin/parties/{pid}/status?status=1", headers=console_headers)
        assert r.status_code == 400


class TestAnnouncements:
    async def test_broadcast_all(self, client, console_headers, student_user, admin_user):
        r = await client.post("/api/v1/admin/announcements", headers=console_headers, json={
            "title": "系统公告", "content": "今晚 2 点维护", "audience": "all",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["recipients"] == 2  # student + admin
        assert data["batch_id"]

    async def test_broadcast_verified_only(self, client, console_headers, student_user):
        # 未认证游客不收
        async with TestSession() as db:
            guest = User(openid=f"guest_{uuid.uuid4().hex[:6]}", nickname="游客",
                         role="guest", is_verified=False)
            db.add(guest)
            await db.commit()

        r = await client.post("/api/v1/admin/announcements", headers=console_headers, json={
            "title": "认证公告", "content": "仅认证可见", "audience": "verified",
        })
        recipients = r.json()["data"]["recipients"]
        assert recipients == 1  # 只有 student_user（console_admin 不在 users 表）

    async def test_recipient_gets_notification(self, client, console_headers, student_user):
        """学生端通知列表出现 announcement 带 title/content。"""
        await client.post("/api/v1/admin/announcements", headers=console_headers, json={
            "title": "标题A", "content": "内容B",
        })
        token = auth_header("x")
        from app.utils.security import create_access_token
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(student_user.id), 'role': 'student'})}"}
        r = await client.get("/api/v1/notifications?type=announcement", headers=headers)
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["payload"]["title"] == "标题A"
        assert items[0]["payload"]["content"] == "内容B"

    async def test_list_history_aggregates_by_batch(self, client, console_headers, student_user):
        await client.post("/api/v1/admin/announcements", headers=console_headers,
                          json={"title": "一", "content": "x"})
        await client.post("/api/v1/admin/announcements", headers=console_headers,
                          json={"title": "二", "content": "y"})
        r = await client.get("/api/v1/admin/announcements", headers=console_headers)
        items = r.json()["data"]["items"]
        assert len(items) == 2  # 两批各一行
        assert items[0]["title"] == "二"  # 倒序

    async def test_broadcast_writes_audit(self, client, console_headers):
        from app.models.admin_log import AdminLog
        await client.post("/api/v1/admin/announcements", headers=console_headers,
                          json={"title": "审计", "content": "x"})
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "announcement.send"))).scalar_one()
            assert log.detail["title"] == "审计"


class TestTrends:
    async def test_returns_day_series(self, client, console_headers, student_user):
        for i in range(3):
            await _mk_post(student_user.id, f"今天的帖{i}")
        r = await client.get("/api/v1/admin/stats/trends?days=7", headers=console_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["days"] == 7
        assert len(data["series"]) == 7
        # 今天（上海时区）有 3 帖
        today = data["series"][-1]
        assert today["posts"] == 3
        # 补零：7 天每天都有值
        assert all("date" in d for d in data["series"])

    async def test_days_bounds_422(self, client, console_headers):
        r = await client.get("/api/v1/admin/stats/trends?days=91", headers=console_headers)
        assert r.status_code == 422


class TestExport:
    async def test_export_posts_csv(self, client, console_headers, student_user):
        await _mk_post(student_user.id, "导出帖")
        r = await client.get("/api/v1/admin/export/posts", headers=console_headers)
        assert r.status_code == 200
        assert "attachment" in r.headers["content-disposition"]
        body = r.text
        assert body.startswith("﻿")  # BOM
        lines = body.strip("﻿").splitlines()
        assert lines[0].startswith("id,post_type")
        assert any("导出帖" in ln for ln in lines[1:])

    async def test_export_users_csv_writes_audit(self, client, console_headers, console_admin):
        from app.models.admin_log import AdminLog
        r = await client.get("/api/v1/admin/export/users", headers=console_headers)
        assert r.status_code == 200
        assert "real_name" in r.text  # 含敏感列
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "export.users"))).scalar_one()
            assert log.admin_id == str(console_admin.id)

    async def test_export_non_admin_403(self, client, student_token):
        r = await client.get("/api/v1/admin/export/users", headers=auth_header(student_token))
        assert r.status_code == 403
