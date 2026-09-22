"""管理后台账号管理测试：列表 / 新建 / 启停 / 强制重置密码。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.services.admin_auth import issue_console_token
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio

PASSWORD = "Admin12345"


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post("/api/v1/admin/auth/login", json={"username": username, "password": password})


class TestAdminAccountList:
    async def test_list_returns_current_admin(self, client: AsyncClient, console_headers: dict, console_admin: AdminUser):
        r = await client.get("/api/v1/admin/admins", headers=console_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["username"] == console_admin.username

    async def test_non_admin_403(self, client: AsyncClient, student_token: str):
        r = await client.get("/api/v1/admin/admins", headers=auth_header(student_token))
        assert r.status_code == 403


class TestAdminAccountCreate:
    async def test_create_then_login(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/admins", headers=console_headers, json={
            "username": "new_admin", "nickname": "新管理员", "password": "NewPass67890",
        })
        assert r.status_code == 200, r.text
        assert r.json()["data"]["username"] == "new_admin"

        login = await _login(client, "new_admin", "NewPass67890")
        assert login.status_code == 200

    async def test_duplicate_username_400(self, client: AsyncClient, console_headers: dict, console_admin: AdminUser):
        r = await client.post("/api/v1/admin/admins", headers=console_headers, json={
            "username": console_admin.username, "nickname": "重复", "password": "NewPass67890",
        })
        assert r.status_code == 400

    async def test_create_writes_audit(self, client: AsyncClient, console_headers: dict):
        from app.models.admin_log import AdminLog
        await client.post("/api/v1/admin/admins", headers=console_headers, json={
            "username": "audit_admin", "nickname": "审计", "password": "NewPass67890",
        })
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "admin.create"))).scalar_one()
            assert log.detail["username"] == "audit_admin"


class TestAdminAccountStatus:
    async def test_cannot_disable_self(self, client: AsyncClient, console_headers: dict, console_admin: AdminUser):
        r = await client.put(f"/api/v1/admin/admins/{console_admin.id}/status",
                             headers=console_headers, json={"is_active": False})
        assert r.status_code == 400
        assert "当前登录" in r.json()["detail"]

    async def test_disable_target_immediately_revokes_token(self, client: AsyncClient, console_headers: dict):
        # 新建一个可被停用的账号
        r = await client.post("/api/v1/admin/admins", headers=console_headers, json={
            "username": "to_disable", "nickname": "待停用", "password": "NewPass67890",
        })
        admin_id = r.json()["data"]["id"]

        async with TestSession() as db:
            target = (await db.execute(select(AdminUser).where(AdminUser.id == admin_id))).scalar_one()
        target_token = issue_console_token(target)

        r = await client.put(f"/api/v1/admin/admins/{admin_id}/status",
                             headers=console_headers, json={"is_active": False})
        assert r.status_code == 200

        # 被停用账号旧 token 立即失效
        r = await client.get("/api/v1/admin/auth/me", headers=auth_header(target_token))
        assert r.status_code == 403

    async def test_disable_nonexistent_404(self, client: AsyncClient, console_headers: dict):
        r = await client.put("/api/v1/admin/admins/00000000-0000-0000-0000-000000000000/status",
                             headers=console_headers, json={"is_active": False})
        assert r.status_code == 404


class TestAdminPasswordReset:
    async def test_reset_password_then_new_login(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/admins", headers=console_headers, json={
            "username": "reset_me", "nickname": "重置对象", "password": "OldPass12345",
        })
        admin_id = r.json()["data"]["id"]

        r = await client.put(f"/api/v1/admin/admins/{admin_id}/password",
                             headers=console_headers, json={"new_password": "BrandNew789"})
        assert r.status_code == 200

        login = await _login(client, "reset_me", "BrandNew789")
        assert login.status_code == 200

    async def test_cannot_reset_self_password(self, client: AsyncClient, console_headers: dict, console_admin: AdminUser):
        r = await client.put(f"/api/v1/admin/admins/{console_admin.id}/password",
                             headers=console_headers, json={"new_password": "BrandNew789"})
        assert r.status_code == 400
        assert "右上角" in r.json()["detail"]
