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
        assert "校园同学_" in body["data"]["user_info"]["nickname"]

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
        assert r.status_code == 400
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
    """Legacy academic verification never reads credentials or grants a role."""
    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [
        {"student_id": "20240001", "password": "old-password"},
        {"student_id": "20240001", "password": "wrong-password"},
        {"student_id": "20240001", "password": "x" * 10000},
        {"password": "never-log-this"},
        {}, {"student_id": None}, {"unknown": "value"},
    ])
    async def test_legacy_endpoint_retired(self, client, guest_user, guest_token, payload):
        response = await client.post("/api/v1/auth/verify", json=payload, headers=auth_header(guest_token))
        assert response.status_code == 410
        assert "never-log-this" not in response.text
        async with TestSession() as db:
            user = await db.get(User, guest_user.id)
            assert user.role == "guest" and not user.is_verified
