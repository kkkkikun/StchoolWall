"""管理后台帖子管理测试：待审队列 / 状态机流转 / moderation 通知 / 看板 / 权限。"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.notification import Notification
from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _seed_post(user_id, content, *, status=0, post_type="general") -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type=post_type, content=content, status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


class TestAdminPostList:
    async def test_pending_queue_filter(self, client: AsyncClient, admin_token: str, student_user: User):
        """?status=0 只返回待审帖。"""
        await _seed_post(student_user.id, "待审A", status=0)
        await _seed_post(student_user.id, "已过审", status=1)
        await _seed_post(student_user.id, "被拒", status=-1)

        resp = await client.get("/api/v1/admin/posts?status=0", headers=auth_header(admin_token))
        assert resp.status_code == 200
        contents = [it["content"] for it in resp.json()["data"]["items"]]
        assert contents == ["被拒"] or contents == ["待审A"]  # 单条
        # 精确断言
        assert set(contents) == {"待审A"}

    async def test_q_search(self, client: AsyncClient, admin_token: str, student_user: User):
        """?q= 对内容模糊搜索。"""
        await _seed_post(student_user.id, "考研自习室搭子")
        await _seed_post(student_user.id, "二手自行车出售")

        resp = await client.get("/api/v1/admin/posts?q=考研", headers=auth_header(admin_token))
        contents = [it["content"] for it in resp.json()["data"]["items"]]
        assert contents == ["考研自习室搭子"]

    async def test_list_contains_all_statuses(self, client: AsyncClient, admin_token: str, student_user: User):
        """无过滤时返回全量（含 0/-1/广告）。"""
        await _seed_post(student_user.id, "正常", status=1)
        await _seed_post(student_user.id, "待审", status=0)
        await _seed_post(student_user.id, "广告", status=1, post_type="advertisement")

        resp = await client.get("/api/v1/admin/posts", headers=auth_header(admin_token))
        contents = [it["content"] for it in resp.json()["data"]["items"]]
        assert set(contents) == {"正常", "待审", "广告"}

    async def test_student_forbidden(self, client: AsyncClient, student_token: str):
        for url in ["/api/v1/admin/posts", "/api/v1/admin/stats"]:
            resp = await client.get(url, headers=auth_header(student_token))
            assert resp.status_code == 403


class TestAdminPostStatus:
    async def test_approve_pending(self, client: AsyncClient, admin_token: str, student_user: User):
        """过审 0→1 后帖子公开可见。"""
        pid = await _seed_post(student_user.id, "过审帖", status=0)

        resp = await client.put(f"/api/v1/admin/posts/{pid}/status?status=1", headers=auth_header(admin_token))
        assert resp.status_code == 200

        pub = (await client.get("/api/v1/posts")).json()["data"]["items"]
        assert any(it["id"] == pid for it in pub)

    async def test_reject_pending_sends_notification(self, client: AsyncClient, admin_token: str, student_user: User):
        """拒审 0→-1：帖子消失 + 作者收到 moderation 通知。"""
        pid = await _seed_post(student_user.id, "违规帖", status=0)

        resp = await client.put(f"/api/v1/admin/posts/{pid}/status?status=-1", headers=auth_header(admin_token))
        assert resp.status_code == 200

        pub = (await client.get("/api/v1/posts")).json()["data"]["items"]
        assert not any(it["id"] == pid for it in pub)

        async with TestSession() as db:
            notifs = (await db.execute(
                select(Notification).where(Notification.user_id == student_user.id)
            )).scalars().all()
            assert len(notifs) == 1
            assert notifs[0].type == "moderation"
            assert notifs[0].post_id == pid
            # 系统通知：actor_id 自指（绕过"不通知自己"）
            assert str(notifs[0].actor_id) == str(student_user.id)

    async def test_ban_and_restore(self, client: AsyncClient, admin_token: str, student_user: User):
        """封禁 1→-1 与恢复 -1→1 往返。"""
        pid = await _seed_post(student_user.id, "来回帖", status=1)

        resp = await client.put(f"/api/v1/admin/posts/{pid}/status?status=-1", headers=auth_header(admin_token))
        assert resp.status_code == 200
        resp = await client.put(f"/api/v1/admin/posts/{pid}/status?status=1", headers=auth_header(admin_token))
        assert resp.status_code == 200

        pub = (await client.get("/api/v1/posts")).json()["data"]["items"]
        assert any(it["id"] == pid for it in pub)

    async def test_invalid_transition_400(self, client: AsyncClient, admin_token: str, student_user: User):
        """非法流转（-2→1）返回 400。"""
        pid = await _seed_post(student_user.id, "已删帖", status=-2)
        resp = await client.put(f"/api/v1/admin/posts/{pid}/status?status=1", headers=auth_header(admin_token))
        assert resp.status_code == 400

    async def test_404(self, client: AsyncClient, admin_token: str):
        resp = await client.put("/api/v1/admin/posts/99999/status?status=1", headers=auth_header(admin_token))
        assert resp.status_code == 404


class TestAdminStats:
    async def test_stats_counts(self, client: AsyncClient, admin_token: str, admin_user: User, student_user: User):
        await _seed_post(student_user.id, "待审1", status=0)
        await _seed_post(student_user.id, "待审2", status=0)
        await _seed_post(student_user.id, "正常", status=1)
        async with TestSession() as db:
            db.add(Report(post_id=await _seed_post(student_user.id, "被举报", status=1),
                          reporter_id=admin_user.id, reason="测试举报"))
            await db.commit()

        resp = await client.get("/api/v1/admin/stats", headers=auth_header(admin_token))
        data = resp.json()["data"]
        assert data["pending_posts"] == 2
        assert data["pending_reports"] == 1
        assert data["total_posts"] == 4  # 待审2 + 正常1 + 被举报目标1
        assert data["total_users"] >= 2  # admin + student
        assert data["frozen_users"] == 0


class TestPostFineFilters:
    """批3：多条件筛选 + page 分页 + 编辑 + 批量。"""

    async def _seed_many(self, student_user, n=15):
        for i in range(n):
            await _seed_post(student_user.id, f"精管帖{i:02d}")

    async def test_filter_by_post_type_and_category(self, client, console_headers, student_user, admin_user):
        await _seed_post(student_user.id, "普通广场帖", status=1, post_type="general")
        async with TestSession() as db:
            db.add(Post(user_id=admin_user.id, post_type="second_hand",
                        content="二手交易帖", status=1, category="二手市场"))
            await db.commit()

        r = await client.get("/api/v1/admin/posts?post_type=second_hand", headers=console_headers)
        contents = [it["content"] for it in r.json()["data"]["items"]]
        assert contents == ["二手交易帖"]

    async def test_filter_by_author(self, client, console_headers, student_user, admin_user):
        await _seed_post(student_user.id, "学生的帖")
        await _seed_post(admin_user.id, "管理员的帖")
        r = await client.get(f"/api/v1/admin/posts?author_id={student_user.id}", headers=console_headers)
        contents = [it["content"] for it in r.json()["data"]["items"]]
        assert contents == ["学生的帖"]

    async def test_time_range_filter(self, client, console_headers, student_user):
        old = await _seed_post(student_user.id, "旧帖")
        await _seed_post(student_user.id, "新帖")
        from sqlalchemy import update
        from datetime import datetime, timedelta, timezone
        async with TestSession() as db:
            await db.execute(update(Post).where(Post.id == old).values(
                created_at=datetime.now(timezone.utc) - timedelta(days=30)))
            await db.commit()

        start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        r = await client.get(f"/api/v1/admin/posts?time_start={start}", headers=console_headers)
        contents = [it["content"] for it in r.json()["data"]["items"]]
        assert contents == ["新帖"]

    async def test_page_pagination_returns_total(self, client, console_headers, student_user):
        await self._seed_many(student_user, 25)
        r = await client.get("/api/v1/admin/posts?page=2&page_size=10", headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 2

    async def test_legacy_cursor_still_works(self, client, console_headers, student_user):
        """旧 cursor 分页不破坏（小程序端兼容）。"""
        await self._seed_many(student_user, 5)
        r = await client.get("/api/v1/admin/posts", headers=console_headers)
        data = r.json()["data"]
        assert "next_cursor" in data and "has_more" in data


class TestPostEdit:
    async def test_edit_content_and_category(self, client, console_headers, student_user):
        pid = await _seed_post(student_user.id, "原始内容", status=1)
        r = await client.put(f"/api/v1/admin/posts/{pid}", headers=console_headers,
                             json={"content": "编辑后内容", "category": "校园广场"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["content"] == "编辑后内容"
        assert data["category"] == "校园广场"

    async def test_edit_partial_fields_only(self, client, console_headers, student_user):
        """只传 content，category 保持原值。"""
        async with TestSession() as db:
            p = Post(user_id=student_user.id, post_type="general", content="原文",
                     status=1, category="树洞倾诉")
            db.add(p); await db.commit(); await db.refresh(p)
            pid = p.id
        r = await client.put(f"/api/v1/admin/posts/{pid}", headers=console_headers,
                             json={"content": "只改文字"})
        assert r.json()["data"]["category"] == "树洞倾诉"

    async def test_edit_nonexistent_404(self, client, console_headers):
        r = await client.put("/api/v1/admin/posts/999999", headers=console_headers,
                             json={"content": "x"})
        assert r.status_code == 404

    async def test_edit_writes_audit(self, client, console_headers, student_user):
        from sqlalchemy import select
        from app.models.admin_log import AdminLog
        pid = await _seed_post(student_user.id, "待编辑")
        await client.put(f"/api/v1/admin/posts/{pid}", headers=console_headers,
                         json={"content": "已编辑"})
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "post.edit"))).scalar_one()
            assert log.target_id == str(pid)


class TestPostBatch:
    async def test_batch_ban_posts(self, client, console_headers, student_user):
        ids = [await _seed_post(student_user.id, f"批量{i}", status=1) for i in range(3)]
        r = await client.post("/api/v1/admin/posts/batch-status", headers=console_headers,
                              json={"post_ids": ids, "status": -1})
        assert r.status_code == 200
        data = r.json()["data"]
        assert sorted(data["succeeded"]) == sorted(ids)
        assert data["failed"] == []

    async def test_batch_reports_partial_failures(self, client, console_headers, student_user):
        """混合不存在/非法流转的 id：逐条报告失败原因。"""
        ok1 = await _seed_post(student_user.id, "可封禁", status=1)
        ok2 = await _seed_post(student_user.id, "待审的", status=0)
        r = await client.post("/api/v1/admin/posts/batch-status", headers=console_headers,
                              json={"post_ids": [ok1, ok2, 999999], "status": -1})
        data = r.json()["data"]
        assert data["succeeded"] == [ok1, ok2]
        assert len(data["failed"]) == 1
        assert data["failed"][0]["id"] == 999999

    async def test_batch_over_limit_400(self, client, console_headers):
        r = await client.post("/api/v1/admin/posts/batch-status", headers=console_headers,
                              json={"post_ids": list(range(101)), "status": -1})
        assert r.status_code == 422

    async def test_batch_writes_audit(self, client, console_headers, student_user):
        from sqlalchemy import select
        from app.models.admin_log import AdminLog
        ids = [await _seed_post(student_user.id, f"审{i}", status=0) for i in range(2)]
        await client.post("/api/v1/admin/posts/batch-status", headers=console_headers,
                          json={"post_ids": ids, "status": 1})
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "post.batch_status"))).scalar_one()
            assert log.detail["count"] == 2



    async def test_handle_report_records_admin(self, client: AsyncClient, admin_token: str, admin_user: User, student_user: User):
        """举报处理后 handled_by/handled_at 落库。"""
        pid = await _seed_post(student_user.id, "举报目标", status=1)
        async with TestSession() as db:
            db.add(Report(post_id=pid, reporter_id=student_user.id, reason="垃圾广告"))
            await db.commit()
            rid = (await db.execute(select(Report).where(Report.post_id == pid))).scalar_one().id

        resp = await client.put(f"/api/v1/admin/reports/{rid}", headers=auth_header(admin_token), json={"action": "dismiss"})
        assert resp.status_code == 200

        async with TestSession() as db:
            r = (await db.execute(select(Report).where(Report.id == rid))).scalar_one()
            assert str(r.handled_by) == str(admin_user.id)
            assert r.handled_at is not None

    async def test_ban_post_sends_moderation_notification(self, client: AsyncClient, admin_token: str, admin_user: User, student_user: User):
        """举报处理 ban_post 时作者收到 moderation 通知。"""
        pid = await _seed_post(student_user.id, "封禁目标", status=1)
        async with TestSession() as db:
            db.add(Report(post_id=pid, reporter_id=student_user.id, reason="人身攻击"))
            await db.commit()
            rid = (await db.execute(select(Report).where(Report.post_id == pid))).scalar_one().id

        resp = await client.put(f"/api/v1/admin/reports/{rid}", headers=auth_header(admin_token), json={"action": "ban_post"})
        assert resp.status_code == 200

        async with TestSession() as db:
            notifs = (await db.execute(
                select(Notification).where(Notification.user_id == student_user.id, Notification.type == "moderation")
            )).scalars().all()
            assert len(notifs) == 1
