"""Admin 模块测试：举报管理、用户管理、权限控制"""

import uuid

import pytest
from httpx import AsyncClient

from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _seed_post(user_id, content="被举报帖", status=1):
    async with TestSession() as db:
        post = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


async def _seed_report(post_id, reporter_id, reason="违规内容"):
    async with TestSession() as db:
        report = Report(
            post_id=post_id, reporter_id=reporter_id,
            reason=reason, description="测试举报", status="pending",
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report


# ============================================================
# GET /api/v1/admin/reports — 举报列表
# ============================================================


class TestListReports:

    @pytest.mark.asyncio
    async def test_admin_list_reports(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 查看举报列表"""
        post = await _seed_post(student_user.id)
        await _seed_report(post.id, student_user.id)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get("/api/v1/admin/reports", headers=auth_header(token))
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["reason"] == "违规内容"

    @pytest.mark.asyncio
    async def test_filter_by_status(self, client: AsyncClient, admin_user: User, student_user: User):
        """按状态过滤举报"""
        post = await _seed_post(student_user.id)
        await _seed_report(post.id, student_user.id)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get("/api/v1/admin/reports?status=pending", headers=auth_header(token))
        assert len(r.json()["data"]["items"]) == 1

        r2 = await client.get("/api/v1/admin/reports?status=resolved", headers=auth_header(token))
        assert len(r2.json()["data"]["items"]) == 0

    @pytest.mark.asyncio
    async def test_student_cannot_list_reports(self, client: AsyncClient, student_user: User):
        """student 不能查看举报列表"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get("/api/v1/admin/reports", headers=auth_header(token))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_rejected(self, client: AsyncClient):
        """无 Token 不能查看"""
        r = await client.get("/api/v1/admin/reports")
        assert r.status_code == 403


# ============================================================
# PUT /api/v1/admin/reports/{id} — 处理举报
# ============================================================


class TestHandleReport:

    @pytest.mark.asyncio
    async def test_dismiss_report(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 驳回举报"""
        post = await _seed_post(student_user.id)
        report = await _seed_report(post.id, student_user.id)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/reports/{report.id}",
            json={"action": "dismiss"}, headers=auth_header(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_ban_post(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 封禁帖子（举报处理后 post.status=-1）"""
        post = await _seed_post(student_user.id)
        report = await _seed_report(post.id, student_user.id)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/reports/{report.id}",
            json={"action": "ban_post"}, headers=auth_header(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_ban_user(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 封禁用户（帖子-1 + 用户冻结）"""
        post = await _seed_post(student_user.id)
        report = await _seed_report(post.id, student_user.id)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/reports/{report.id}",
            json={"action": "ban_user"}, headers=auth_header(token),
        )
        assert r.status_code == 200

        # 验证用户已被冻结
        async with TestSession() as db:
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.id == student_user.id))
            user = result.scalar_one()
            assert user.status == 0

    @pytest.mark.asyncio
    async def test_handle_nonexistent_report(self, client: AsyncClient, admin_user: User):
        """处理不存在的举报返回 404"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            "/api/v1/admin/reports/99999",
            json={"action": "dismiss"}, headers=auth_header(token),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_handle_twice(self, client: AsyncClient, admin_user: User, student_user: User):
        """已处理的举报不能重复处理"""
        post = await _seed_post(student_user.id)
        report = await _seed_report(post.id, student_user.id)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        await client.put(
            f"/api/v1/admin/reports/{report.id}",
            json={"action": "dismiss"}, headers=auth_header(token),
        )
        r = await client.put(
            f"/api/v1/admin/reports/{report.id}",
            json={"action": "dismiss"}, headers=auth_header(token),
        )
        assert r.status_code == 400


# ============================================================
# GET /api/v1/admin/users — 用户列表
# ============================================================


class TestListUsers:

    @pytest.mark.asyncio
    async def test_admin_list_users(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 查看用户列表"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get("/api/v1/admin/users", headers=auth_header(token))
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) >= 2

    @pytest.mark.asyncio
    async def test_student_cannot_list_users(self, client: AsyncClient, student_user: User):
        """student 不能查看用户列表"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get("/api/v1/admin/users", headers=auth_header(token))
        assert r.status_code == 403


# ============================================================
# PUT /api/v1/admin/users/{id}/status — 冻结/解冻用户
# ============================================================


class TestUpdateUserStatus:

    @pytest.mark.asyncio
    async def test_freeze_user(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 冻结用户"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/users/{student_user.id}/status?status=0",
            headers=auth_header(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 0

    @pytest.mark.asyncio
    async def test_unfreeze_user(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 解冻用户"""
        # 先冻结
        async with TestSession() as db:
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.id == student_user.id))
            user = result.scalar_one()
            user.status = 0
            await db.commit()

        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/users/{student_user.id}/status?status=1",
            headers=auth_header(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 1

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, client: AsyncClient, admin_user: User):
        """不存在的用户返回 404"""
        fake_id = str(uuid.uuid4())
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/users/{fake_id}/status?status=0",
            headers=auth_header(token),
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_student_cannot_freeze(self, client: AsyncClient, student_user: User):
        """student 不能冻结用户"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            f"/api/v1/admin/users/{student_user.id}/status?status=0",
            headers=auth_header(token),
        )
        assert r.status_code == 403
