"""管理后台（console）账号密码体系测试。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.admin_user import AdminUser
from app.services.admin_auth import issue_console_token
from app.utils.password import hash_password, verify_password
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio

PASSWORD = "Admin12345"


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post("/api/v1/admin/auth/login", json={"username": username, "password": password})


class TestLogin:
    async def test_login_success_returns_token(self, client: AsyncClient, console_admin: AdminUser):
        r = await _login(client, console_admin.username, PASSWORD)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["access_token"]
        assert data["admin"]["username"] == console_admin.username
        assert data["admin"]["nickname"]

    async def test_login_updates_last_login_at(self, client: AsyncClient, console_admin: AdminUser):
        await _login(client, console_admin.username, PASSWORD)
        async with TestSession() as db:
            admin = (await db.execute(select(AdminUser).where(AdminUser.id == console_admin.id))).scalar_one()
            assert admin.last_login_at is not None

    async def test_login_wrong_password_401(self, client: AsyncClient, console_admin: AdminUser):
        r = await _login(client, console_admin.username, "WrongPass999")
        assert r.status_code == 401

    async def test_login_unknown_user_401(self, client: AsyncClient):
        r = await _login(client, "no_such_admin", "whatever123")
        assert r.status_code == 401

    async def test_login_inactive_admin_401(self, client: AsyncClient, console_admin: AdminUser):
        async with TestSession() as db:
            admin = (await db.execute(select(AdminUser).where(AdminUser.id == console_admin.id))).scalar_one()
            admin.is_active = False
            await db.commit()
        r = await _login(client, console_admin.username, PASSWORD)
        assert r.status_code == 401

    async def test_login_missing_fields_422(self, client: AsyncClient):
        r = await client.post("/api/v1/admin/auth/login", json={"username": "x"})
        assert r.status_code == 422

    async def test_login_rate_limited(self, client: AsyncClient, console_admin: AdminUser):
        # 连续 10 次失败触发限流（Redis 每测试清空）
        for _ in range(10):
            await _login(client, console_admin.username, "bad")
        r = await _login(client, console_admin.username, PASSWORD)
        assert r.status_code == 429


class TestMe:
    async def test_me_with_console_token(self, client: AsyncClient, console_headers: dict, console_admin: AdminUser):
        r = await client.get("/api/v1/admin/auth/me", headers=console_headers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["source"] == "console"
        assert data["display_name"] == console_admin.nickname

    async def test_me_with_garbage_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/admin/auth/me", headers=auth_header("garbage.token.here"))
        assert r.status_code == 401

    async def test_console_token_rejected_after_deactivate(
        self, client: AsyncClient, console_headers: dict, console_admin: AdminUser
    ):
        async with TestSession() as db:
            admin = (await db.execute(select(AdminUser).where(AdminUser.id == console_admin.id))).scalar_one()
            admin.is_active = False
            await db.commit()
        r = await client.get("/api/v1/admin/auth/me", headers=console_headers)
        assert r.status_code == 403

    async def test_student_token_rejected_403(self, client: AsyncClient, student_token: str):
        r = await client.get("/api/v1/admin/auth/me", headers=auth_header(student_token))
        assert r.status_code == 403

    async def test_legacy_users_admin_token_accepted(self, client: AsyncClient, admin_token: str):
        """双 token 兼容：小程序体系 users.role=admin 的 token 仍可过 require_admin_console。"""
        r = await client.get("/api/v1/admin/auth/me", headers=auth_header(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["source"] == "legacy"


class TestChangePassword:
    async def test_change_password_success_old_token_invalid(
        self, client: AsyncClient, console_headers: dict, console_admin: AdminUser
    ):
        """改密成功后 pwd_version+1，旧 token 立即失效。"""
        r = await client.put("/api/v1/admin/auth/password", headers=console_headers, json={
            "old_password": PASSWORD, "new_password": "NewPass67890",
        })
        assert r.status_code == 200

        # 旧 token 已失效
        r = await client.get("/api/v1/admin/auth/me", headers=console_headers)
        assert r.status_code == 401

        # 新密码能登录
        r = await _login(client, console_admin.username, "NewPass67890")
        assert r.status_code == 200

    async def test_change_password_wrong_old_400(self, client: AsyncClient, console_headers: dict):
        r = await client.put("/api/v1/admin/auth/password", headers=console_headers, json={
            "old_password": "BadOld111", "new_password": "NewPass67890",
        })
        assert r.status_code == 400

    async def test_change_password_too_short_422(self, client: AsyncClient, console_headers: dict):
        r = await client.put("/api/v1/admin/auth/password", headers=console_headers, json={
            "old_password": PASSWORD, "new_password": "short",
        })
        assert r.status_code == 422

    async def test_legacy_actor_cannot_change_password(self, client: AsyncClient, admin_token: str):
        """legacy（小程序体系）token 无密码概念，不能改。"""
        r = await client.put("/api/v1/admin/auth/password", headers=auth_header(admin_token), json={
            "old_password": "x", "new_password": "NewPass67890",
        })
        assert r.status_code == 403


class TestPasswordUtils:
    def test_hash_verify_roundtrip(self):
        h = hash_password("S3cret!pass")
        assert h != "S3cret!pass"
        assert verify_password("S3cret!pass", h)
        assert not verify_password("wrong", h)
        # 同密码两次哈希不同（盐随机）
        assert hash_password("S3cret!pass") != h

    def test_verify_corrupted_hash_false(self):
        assert not verify_password("x", "not-a-bcrypt-hash")


class TestCreateAdminCli:
    async def test_create_admin_idempotent(self):
        from app.services.admin_auth import create_or_reset_admin

        async with TestSession() as db:
            admin1, created1 = await create_or_reset_admin(db, "cli_test_admin", "CLI管理员", "Passw0rd123")
            admin2, created2 = await create_or_reset_admin(db, "cli_test_admin", "CLI管理员", "Passw0rd123")
            assert created1 is True
            assert created2 is False
            assert admin1.id == admin2.id

    async def test_reset_admin_updates_password(self):
        from app.services.admin_auth import create_or_reset_admin

        async with TestSession() as db:
            _, _ = await create_or_reset_admin(db, "cli_reset_admin", "", "Passw0rd123")
            admin, created = await create_or_reset_admin(db, "cli_reset_admin", "", "NewPass45678", reset=True)
            assert created is False
            assert verify_password("NewPass45678", admin.password_hash)
