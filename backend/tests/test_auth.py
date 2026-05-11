"""Auth 模块测试：微信登录 + 学籍认证 + 限流"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _mock_wx_response(data: dict):
    """构造模拟的 httpx.Response"""
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _mock_async_client(get_return=None):
    """构造模拟的 httpx.AsyncClient（支持 async with）"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=get_return)
    mock_client.post = AsyncMock(return_value=_mock_wx_response({}))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ============================================================
# 微信静默登录 POST /api/v1/auth/login
# ============================================================


class TestWxLogin:
    """微信静默登录"""

    @pytest.mark.asyncio
    async def test_new_user_creates_guest(self, client: AsyncClient):
        """首次登录 -> 自动创建 guest 用户 -> 返回 JWT"""
        mock_client = _mock_async_client(
            _mock_wx_response({"openid": "wx_new_001", "session_key": "sk"})
        )
        with patch("app.services.auth.httpx.AsyncClient", return_value=mock_client):
            r = await client.post("/api/v1/auth/login", json={"code": "valid_code"})
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["role"] == "guest"
        assert body["data"]["user_info"]["is_verified"] is False
        assert "access_token" in body["data"]
        assert "鄂应学子_" in body["data"]["user_info"]["nickname"]

    @pytest.mark.asyncio
    async def test_returning_user_gets_existing_role(self, client: AsyncClient, student_user: User):
        """已有 student 用户再次登录 -> 返回 student 角色"""
        mock_client = _mock_async_client(
            _mock_wx_response({"openid": student_user.openid, "session_key": "sk"})
        )
        with patch("app.services.auth.httpx.AsyncClient", return_value=mock_client):
            r = await client.post("/api/v1/auth/login", json={"code": "valid_code"})
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["role"] == "student"
        assert body["data"]["user_info"]["is_verified"] is True
        assert body["data"]["user_info"]["id"] == str(student_user.id)

    @pytest.mark.asyncio
    async def test_invalid_code_returns_error(self, client: AsyncClient):
        """无效 code（微信返回 errcode）-> 报错"""
        mock_client = _mock_async_client(
            _mock_wx_response({"errcode": 40029, "errmsg": "invalid code"})
        )
        with patch("app.services.auth.httpx.AsyncClient", return_value=mock_client):
            r = await client.post("/api/v1/auth/login", json={"code": "bad_code"})
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 400
        assert "失败" in body["message"]

    @pytest.mark.asyncio
    async def test_missing_code_field(self, client: AsyncClient):
        """缺少 code 字段 -> 422"""
        r = await client.post("/api/v1/auth/login", json={})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_code_field(self, client: AsyncClient):
        """空 code -> 422"""
        r = await client.post("/api/v1/auth/login", json={"code": ""})
        assert r.status_code == 422


# ============================================================
# 学籍认证绑定 POST /api/v1/auth/verify
# ============================================================


class TestStudentVerify:
    """学籍认证绑定"""

    @pytest.mark.asyncio
    async def test_verify_success(self, client: AsyncClient, guest_user: User):
        """guest 认证成功 -> 升级为 student，real_name 落库"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        mock_result = {"status": "success", "msg": "登录成功", "real_name": "测试张三"}
        with patch("app.services.auth.verify_student", AsyncMock(return_value=mock_result)):
            r = await client.post(
                "/api/v1/auth/verify",
                json={"student_id": "20249990001", "password": "test123"},
                headers=auth_header(token),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["message"] == "认证成功"
        assert body["data"]["role"] == "student"
        assert "access_token" in body["data"]

        # 验证数据库：real_name 和 is_verified 已落库
        async with TestSession() as db:
            result = await db.execute(select(User).where(User.id == guest_user.id))
            updated = result.scalar_one()
            assert updated.real_name == "测试张三"
            assert updated.is_verified is True
            assert updated.student_id == "20249990001"
            assert updated.role == "student"

    @pytest.mark.asyncio
    async def test_verify_wrong_password(self, client: AsyncClient, guest_user: User):
        """教务系统密码错误 -> 认证失败"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        mock_result = {"status": "fail", "msg": "登录失败: 用户名或密码错误"}
        with patch("app.services.auth.verify_student", AsyncMock(return_value=mock_result)):
            r = await client.post(
                "/api/v1/auth/verify",
                json={"student_id": "20249990001", "password": "wrong"},
                headers=auth_header(token),
            )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 400
        assert "失败" in body["message"]

    @pytest.mark.asyncio
    async def test_verify_student_id_already_bound(self, client: AsyncClient, guest_user: User, student_user: User):
        """学号已被其他用户绑定 -> 409"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.post(
            "/api/v1/auth/verify",
            json={"student_id": student_user.student_id, "password": "any"},
            headers=auth_header(token),
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_verify_already_verified(self, client: AsyncClient, student_user: User):
        """已完成认证的用户再次认证 -> 拒绝"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(
            "/api/v1/auth/verify",
            json={"student_id": "2024NEW001", "password": "test"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 400
        assert "已完成" in body["message"]

    @pytest.mark.asyncio
    async def test_verify_requires_token(self, client: AsyncClient):
        """无 Token -> 403"""
        r = await client.post(
            "/api/v1/auth/verify",
            json={"student_id": "20240001", "password": "test"},
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_verify_missing_fields(self, client: AsyncClient, guest_user: User):
        """缺少必填字段 -> 422"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.post(
            "/api/v1/auth/verify",
            json={"student_id": "20240001"},
            headers=auth_header(token),
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_verify_rate_limit_by_ip(self, client: AsyncClient, guest_user: User):
        """IP 限流：超过 10 次/分钟 -> 429"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        mock_result = {"status": "fail", "msg": "登录失败"}

        with patch("app.services.auth.verify_student", AsyncMock(return_value=mock_result)):
            for _ in range(10):
                r = await client.post(
                    "/api/v1/auth/verify",
                    json={"student_id": f"2024{_}", "password": "t"},
                    headers=auth_header(token),
                )
            # 第 11 次应被限流
            r = await client.post(
                "/api/v1/auth/verify",
                json={"student_id": "2024overflow", "password": "t"},
                headers=auth_header(token),
            )
        assert r.status_code == 429
