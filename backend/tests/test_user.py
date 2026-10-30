"""User 模块测试：个人资料查看与更新"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import auth_header
from tests.production_helpers import approve_profile


# ============================================================
# GET /api/v1/user/profile
# ============================================================


class TestGetProfile:
    """获取个人资料"""

    @pytest.mark.asyncio
    async def test_student_can_see_own_profile(self, client: AsyncClient, student_user: User):
        """student 用户可查看自己的完整资料（含 real_name）"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["nickname"] == student_user.nickname
        assert data["real_name"] == student_user.real_name
        assert data["student_id"] == student_user.student_id
        assert data["wechat_id"] == student_user.wechat_id

    @pytest.mark.asyncio
    async def test_admin_can_see_own_profile(self, client: AsyncClient, admin_user: User):
        """admin 用户可查看自己的完整资料"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["nickname"] == admin_user.nickname
        assert data["real_name"] == admin_user.real_name

    @pytest.mark.asyncio
    async def test_guest_forbidden(self, client: AsyncClient, guest_user: User):
        """guest 角色无权查看个人资料 -> 403"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_forbidden(self, client: AsyncClient):
        """无 Token -> 401"""
        r = await client.get("/api/v1/user/profile")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_unauthorized(self, client: AsyncClient):
        """伪造 Token -> 401"""
        r = await client.get("/api/v1/user/profile", headers=auth_header("fake.token.here"))
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_in_db_unauthorized(self, client: AsyncClient):
        """Token 中用户不存在于数据库 -> 401"""
        import uuid
        fake_id = str(uuid.uuid4())
        token = create_access_token({"sub": fake_id, "role": "student"})
        r = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_frozen_user_forbidden(self, client: AsyncClient):
        """status=0 被冻结的用户 -> 403"""
        from tests.conftest import _create_user

        user = await _create_user(
            openid="test_frozen_001",
            nickname="冻结用户",
            role="student",
            is_verified=True,
            status=0,
        )
        token = create_access_token({"sub": str(user.id), "role": "student"})
        r = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r.status_code == 403


# ============================================================
# PUT /api/v1/user/profile
# ============================================================


class TestUpdateProfile:
    """更新用户资料"""

    @pytest.mark.asyncio
    async def test_update_nickname(self, client: AsyncClient, student_user: User):
        """更新昵称"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": "新昵称"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 待审不立即公开，审核后更新
        await approve_profile(r.json()["data"]["job_id"])
        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r2.json()["data"]["nickname"] == "新昵称"

    @pytest.mark.asyncio
    async def test_update_wechat_id(self, client: AsyncClient, student_user: User):
        """更新微信号"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/profile",
            json={"wechat_id": "wx_new_id"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        await approve_profile(r.json()["data"]["job_id"])

        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r2.json()["data"]["wechat_id"] == "wx_new_id"

    @pytest.mark.asyncio
    async def test_update_both_fields(self, client: AsyncClient, student_user: User):
        """同时更新昵称和微信号"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": "双改昵称", "wechat_id": "wx_both"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        await approve_profile(r.json()["data"]["job_id"])

        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        data = r2.json()["data"]
        assert data["nickname"] == "双改昵称"
        assert data["wechat_id"] == "wx_both"

    @pytest.mark.asyncio
    async def test_update_nothing(self, client: AsyncClient, student_user: User):
        """不传任何字段 -> 不报错，原值不变"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/profile",
            json={},
            headers=auth_header(token),
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_guest_forbidden(self, client: AsyncClient, guest_user: User):
        """guest 角色无权修改资料 -> 403"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": "不应该成功"},
            headers=auth_header(token),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_forbidden(self, client: AsyncClient):
        """无 Token -> 401"""
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": "无Token"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_real_name_not_changeable(self, client: AsyncClient, student_user: User):
        """real_name 和 student_id 不可通过此接口修改（schema 中无此字段）"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        original_name = student_user.real_name
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": "改昵称"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        await approve_profile(r.json()["data"]["job_id"])

        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r2.json()["data"]["real_name"] == original_name

    @pytest.mark.asyncio
    async def test_nickname_too_long(self, client: AsyncClient, student_user: User):
        """昵称超长 -> 422"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": "A" * 51},
            headers=auth_header(token),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_nickname_rejected(self, client: AsyncClient, student_user: User):
        """空昵称 -> 422"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/profile",
            json={"nickname": ""},
            headers=auth_header(token),
        )
        assert r.status_code == 422
