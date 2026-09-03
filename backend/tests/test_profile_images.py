"""头像/横幅更换测试：PUT /user/profile 持久化 avatar_url 与 banner_url。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


class TestAvatarBanner:

    @pytest.mark.asyncio
    async def test_update_and_readback(self, client: AsyncClient, student_user: User):
        token = _token(student_user)
        r = await client.put(
            "/api/v1/user/profile",
            json={"avatar_url": "/static/uploads/avatars/a.png", "banner_url": "/static/uploads/banners/b.jpg"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        # 读回
        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        data = r2.json()["data"]
        assert data["avatar_url"] == "/static/uploads/avatars/a.png"
        assert data["banner_url"] == "/static/uploads/banners/b.jpg"

    @pytest.mark.asyncio
    async def test_partial_update_keeps_other_fields(self, client: AsyncClient, student_user: User):
        """只换头像时横幅不被清掉。"""
        token = _token(student_user)
        await client.put("/api/v1/user/profile", json={"banner_url": "/b.jpg"}, headers=auth_header(token))
        await client.put("/api/v1/user/profile", json={"avatar_url": "/a.png"}, headers=auth_header(token))
        r = await client.get("/api/v1/user/profile", headers=auth_header(token))
        data = r.json()["data"]
        assert data["avatar_url"] == "/a.png"
        assert data["banner_url"] == "/b.jpg"

    @pytest.mark.asyncio
    async def test_require_login(self, client: AsyncClient):
        r = await client.put("/api/v1/user/profile", json={"avatar_url": "/a.png"})
        assert r.status_code == 403


class TestBio:

    @pytest.mark.asyncio
    async def test_bio_roundtrip(self, client: AsyncClient, student_user: User):
        token = _token(student_user)
        r = await client.put(
            "/api/v1/user/profile",
            json={"bio": "热爱生活，热爱分享～"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r2.json()["data"]["bio"] == "热爱生活，热爱分享～"

    @pytest.mark.asyncio
    async def test_bio_too_long_rejected(self, client: AsyncClient, student_user: User):
        token = _token(student_user)
        r = await client.put(
            "/api/v1/user/profile",
            json={"bio": "x" * 201},
            headers=auth_header(token),
        )
        assert r.status_code == 422  # 上限 200
