"""dev-login（开发环境一键登录）测试。"""

import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_dev_login_returns_token(client: AsyncClient):
    """development 环境返回 student token"""
    settings.ENVIRONMENT = "development"
    try:
        r = await client.post("/api/v1/auth/dev-login")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "access_token" in data
        assert data["role"] == "student"
        assert data["user_info"]["nickname"]
    finally:
        settings.ENVIRONMENT = "test"


@pytest.mark.asyncio
async def test_dev_login_blocked_in_non_dev(client: AsyncClient):
    """非 development 环境（conftext 默认 test）-> 404"""
    r = await client.post("/api/v1/auth/dev-login")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_dev_login_is_idempotent(client: AsyncClient):
    """重复 dev-login 复用同一演示账号（openid 固定）"""
    settings.ENVIRONMENT = "development"
    try:
        r1 = await client.post("/api/v1/auth/dev-login")
        r2 = await client.post("/api/v1/auth/dev-login")
        assert r1.json()["data"]["user_info"]["id"] == r2.json()["data"]["user_info"]["id"]
    finally:
        settings.ENVIRONMENT = "test"


@pytest.mark.asyncio
async def test_dev_login_admin_role(client: AsyncClient):
    """?as_admin=true 登演示管理员（管理后台联调）"""
    settings.ENVIRONMENT = "development"
    try:
        r = await client.post("/api/v1/auth/dev-login?as_admin=true")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["role"] == "admin"

        # admin token 能访问管理接口
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        stats = await client.get("/api/v1/admin/stats", headers=headers)
        assert stats.status_code == 200

        # 学生/管理员是两个不同账号
        student = await client.post("/api/v1/auth/dev-login")
        assert student.json()["data"]["user_info"]["id"] != data["user_info"]["id"]
    finally:
        settings.ENVIRONMENT = "test"
