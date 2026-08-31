"""管理后台用户精细管理测试：搜索/筛选/改角色/详情。"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _mk_user(**kw) -> User:
    defaults = dict(
        openid=f"u_{uuid.uuid4().hex[:8]}",
        nickname="用户",
        role="guest",
        is_verified=False,
    )
    defaults.update(kw)
    async with TestSession() as db:
        u = User(**defaults)
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u


class TestUserList:
    async def test_search_by_nickname(self, client: AsyncClient, console_headers: dict):
        await _mk_user(nickname="张三丰")
        await _mk_user(nickname="李四")
        r = await client.get("/api/v1/admin/users?q=张三丰", headers=console_headers)
        names = [u["nickname"] for u in r.json()["data"]["items"]]
        assert names == ["张三丰"]

    async def test_search_by_student_id(self, client: AsyncClient, console_headers: dict):
        await _mk_user(nickname="有学号", student_id="20991234")
        r = await client.get("/api/v1/admin/users?q=20991234", headers=console_headers)
        assert [u["nickname"] for u in r.json()["data"]["items"]] == ["有学号"]

    async def test_filter_by_role_and_verified(self, client: AsyncClient, console_headers: dict):
        await _mk_user(nickname="学生A", role="student", is_verified=True)
        await _mk_user(nickname="游客B", role="guest", is_verified=False)
        r = await client.get("/api/v1/admin/users?role=student&is_verified=true", headers=console_headers)
        assert [u["nickname"] for u in r.json()["data"]["items"]] == ["学生A"]

    async def test_filter_by_status_frozen(self, client: AsyncClient, console_headers: dict):
        await _mk_user(nickname="冻结的", status=0)
        await _mk_user(nickname="正常的", status=1)
        r = await client.get("/api/v1/admin/users?status=0", headers=console_headers)
        assert [u["nickname"] for u in r.json()["data"]["items"]] == ["冻结的"]

    async def test_page_pagination_returns_total(self, client: AsyncClient, console_headers: dict):
        for i in range(15):
            await _mk_user(nickname=f"分页{i:02d}")
        r = await client.get("/api/v1/admin/users?page=2&page_size=10", headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 15
        assert len(data["items"]) == 5
        assert data["page"] == 2
        assert data["page_size"] == 10

    async def test_time_range_filter(self, client: AsyncClient, console_headers: dict):
        from sqlalchemy import update
        old = await _mk_user(nickname="老用户")
        new = await _mk_user(nickname="新用户")
        async with TestSession() as db:
            await db.execute(update(User).where(User.id == old.id).values(
                created_at=datetime.now(timezone.utc) - timedelta(days=30)))
            await db.commit()

        start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        r = await client.get(f"/api/v1/admin/users?time_start={start}", headers=console_headers)
        names = [u["nickname"] for u in r.json()["data"]["items"]]
        assert "新用户" in names
        assert "老用户" not in names


class TestUserRole:
    async def test_change_role_guest_to_student(self, client: AsyncClient, console_headers: dict):
        u = await _mk_user(nickname="待升级")
        r = await client.put(f"/api/v1/admin/users/{u.id}/role", headers=console_headers,
                             json={"role": "student"})
        assert r.status_code == 200
        assert r.json()["data"]["role"] == "student"

    async def test_invalid_role_422(self, client: AsyncClient, console_headers: dict):
        u = await _mk_user()
        r = await client.put(f"/api/v1/admin/users/{u.id}/role", headers=console_headers,
                             json={"role": "superadmin"})
        assert r.status_code == 422

    async def test_legacy_actor_cannot_demote_self(self, client: AsyncClient, admin_token: str, admin_user):
        """legacy（小程序体系）管理员不能降自己的角色（防锁死）。"""
        r = await client.put(f"/api/v1/admin/users/{admin_user.id}/role",
                             headers=auth_header(admin_token), json={"role": "student"})
        assert r.status_code == 400

    async def test_role_change_writes_audit(self, client: AsyncClient, console_headers: dict):
        from sqlalchemy import select
        from app.models.admin_log import AdminLog
        u = await _mk_user()
        await client.put(f"/api/v1/admin/users/{u.id}/role", headers=console_headers,
                         json={"role": "admin"})
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "user.role"))).scalar_one()
            assert log.target_id == str(u.id)


class TestUserDetail:
    async def test_detail_aggregates_counts(self, client: AsyncClient, console_headers: dict, admin_user):
        u = await _mk_user(nickname="详情用户", role="student", is_verified=True, student_id="20990001",
                           real_name="真名")
        async with TestSession() as db:
            for i in range(3):
                db.add(Post(user_id=u.id, post_type="general", content=f"帖{i}", status=1))
            await db.flush()
            first_post = (await db.execute(
                select(Post).where(Post.user_id == u.id).order_by(Post.id)
            )).scalars().first()
            db.add(Report(post_id=first_post.id, reporter_id=admin_user.id, reason="x"))
            await db.commit()

        r = await client.get(f"/api/v1/admin/users/{u.id}", headers=console_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["nickname"] == "详情用户"
        assert data["posts_count"] == 3
        assert "recent_posts" in data
        assert len(data["recent_posts"]) == 3

    async def test_detail_404(self, client: AsyncClient, console_headers: dict):
        r = await client.get("/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
                             headers=console_headers)
        assert r.status_code == 404
