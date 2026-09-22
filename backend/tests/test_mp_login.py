"""公众号网页授权登录测试：code 换 openid + 新用户 guest + 老用户保留身份。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import httpx as httpx_lib
from app.config import settings
from app.models.user import User
from tests.conftest import TestSession


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class TestMpLogin:
    @pytest.mark.asyncio
    async def test_new_user_creates_guest(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "WECHAT_MP_APP_ID", "mp_app_id")
        monkeypatch.setattr(settings, "WECHAT_MP_APP_SECRET", "mp_app_secret")

        async def fake_get(self, url, timeout=None):
            return FakeResp({"openid": "oauth_openid_001"})

        monkeypatch.setattr(httpx_lib.AsyncClient, "get", fake_get)

        r = await client.post("/api/v1/auth/mp-login", json={"code": "test_code"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["role"] == "guest"
        assert data["user_info"]["is_verified"] is False

        async with TestSession() as db:
            u = (await db.execute(
                select(User).where(User.openid == "mp:oauth_openid_001")
            )).scalar_one()
            assert u.role == "guest"
            assert u.is_verified is False

    @pytest.mark.asyncio
    async def test_returning_user_keeps_role(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "WECHAT_MP_APP_ID", "mp_app_id")
        monkeypatch.setattr(settings, "WECHAT_MP_APP_SECRET", "mp_app_secret")

        async with TestSession() as db:
            db.add(User(openid="mp:oauth_openid_002", nickname="老用户", role="student", is_verified=True))
            await db.commit()

        async def fake_get(self, url, timeout=None):
            return FakeResp({"openid": "oauth_openid_002"})

        monkeypatch.setattr(httpx_lib.AsyncClient, "get", fake_get)

        r = await client.post("/api/v1/auth/mp-login", json={"code": "test_code"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["role"] == "student"
        assert data["user_info"]["nickname"] == "老用户"
        assert data["user_info"]["is_verified"] is True

    @pytest.mark.asyncio
    async def test_not_configured_returns_400(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "WECHAT_MP_APP_ID", "")
        monkeypatch.setattr(settings, "WECHAT_MP_APP_SECRET", "")
        r = await client.post("/api/v1/auth/mp-login", json={"code": "test_code"})
        assert r.status_code == 400
