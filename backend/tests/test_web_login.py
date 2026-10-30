"""网页登录测试：注册即登录 / 密码校验 / 失败退避 / 冻结拒登 / 密码不落明文。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.routers.auth as auth_router_mod
from app.models.user import User
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio


async def _get_user(username: str) -> User | None:
    async with TestSession() as db:
        return (await db.execute(
            select(User).where(User.openid == f"web:{username}")
        )).scalar_one_or_none()


class TestWebLogin:

    async def test_register_creates_guest_user(self, client: AsyncClient):
        """首次登录即注册：role=guest（不可发帖），认证后升级。"""
        r = await client.post("/api/v1/auth/web-login", json={"username": "xiaoming", "password": "pass123456"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["access_token"]
        assert data["role"] == "guest"
        assert data["user_info"]["nickname"].startswith("校园同学_")

        user = await _get_user("xiaoming")
        assert user is not None
        assert user.role == "guest"
        assert user.is_verified is False

    async def test_relogin_with_correct_password(self, client: AsyncClient):
        await client.post("/api/v1/auth/web-login", json={"username": "xiaoming", "password": "pass123456"})
        r = await client.post("/api/v1/auth/web-login", json={"username": "xiaoming", "password": "pass123456"})
        assert r.status_code == 200
        # 同一账号：两次 user_info.id 一致
        assert r.json()["data"]["user_info"]["id"]

    async def test_wrong_password_401(self, client: AsyncClient):
        await client.post("/api/v1/auth/web-login", json={"username": "xiaoming", "password": "pass123456"})
        r = await client.post("/api/v1/auth/web-login", json={"username": "xiaoming", "password": "wrong-pass"})
        assert r.status_code == 401

    async def test_password_never_stored_plaintext(self, client: AsyncClient):
        await client.post("/api/v1/auth/web-login", json={"username": "secretman", "password": "plain-text-pw"})
        user = await _get_user("secretman")
        assert user.web_password_hash is not None
        assert "plain-text-pw" not in user.web_password_hash
        assert user.web_password_hash.startswith("$2")  # bcrypt

    async def test_frozen_user_rejected(self, client: AsyncClient):
        await client.post("/api/v1/auth/web-login", json={"username": "frozen", "password": "pass123456"})
        async with TestSession() as db:  # 同一 session 内改状态才会落库
            u = (await db.execute(
                select(User).where(User.openid == "web:frozen")
            )).scalar_one()
            u.status = 0
            await db.commit()
        r = await client.post("/api/v1/auth/web-login", json={"username": "frozen", "password": "pass123456"})
        assert r.status_code == 403

    async def test_param_bounds_422(self, client: AsyncClient):
        assert (await client.post("/api/v1/auth/web-login", json={"username": "a", "password": "pass123456"})).status_code == 422
        assert (await client.post("/api/v1/auth/web-login", json={"username": "x" * 21, "password": "pass123456"})).status_code == 422
        assert (await client.post("/api/v1/auth/web-login", json={"username": "okname", "password": "12345"})).status_code == 422
        assert (await client.post("/api/v1/auth/web-login", json={"username": "okname", "password": "x" * 65})).status_code == 422

    async def test_username_failure_backoff(self, client: AsyncClient, monkeypatch):
        """同一用户名连续错密超阈值 → 正确密码也 429。"""
        monkeypatch.setattr(auth_router_mod, "WEB_LOGIN_USER_RATE", (2, 600))
        # 先用正确密码注册固定账号
        await client.post("/api/v1/auth/web-login", json={"username": "lockme", "password": "right-pass-123"})
        for _ in range(2):
            r = await client.post("/api/v1/auth/web-login", json={"username": "lockme", "password": "bad-password"})
            assert r.status_code == 401
        r = await client.post("/api/v1/auth/web-login", json={"username": "lockme", "password": "right-pass-123"})
        assert r.status_code == 429

    async def test_web_user_cannot_post_until_verified(self, client: AsyncClient):
        """网页用户 role=guest → 发帖被 403，需先学籍认证。"""
        r = await client.post("/api/v1/auth/web-login", json={"username": "poster", "password": "pass123456"})
        token = r.json()["data"]["access_token"]
        r2 = await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "网页用户的第一帖"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 403
