import time

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.admin_log import AdminLog
from app.models.admin_user import AdminUser
from app.services.admin_auth import issue_console_token
from app.utils.mfa import totp_code
from app.utils.password import hash_password
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio
PASSWORD = "Admin12345"


@pytest.fixture(autouse=True)
def mfa_test_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_MFA_ENCRYPTION_KEY", "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=")


async def _ordinary_admin(username="ordinary_admin") -> AdminUser:
    async with TestSession() as db:
        admin = AdminUser(username=username, nickname="普通管理员", role="admin",
                          password_hash=hash_password(PASSWORD))
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin


async def test_regular_admin_cannot_manage_accounts_or_runtime_controls(client):
    admin = await _ordinary_admin()
    headers = auth_header(issue_console_token(admin))
    response = await client.post("/api/v1/admin/admins", headers=headers, json={
        "username": "forbidden_admin", "nickname": "不应创建", "password": "NewPass67890",
    })
    assert response.status_code == 403
    response = await client.get("/api/v1/admin/runtime-controls", headers=headers)
    assert response.status_code == 403
    response = await client.put("/api/v1/admin/runtime-controls", headers=headers,
                                json={"publishing_enabled": False})
    assert response.status_code == 403


async def test_owner_can_create_peer_and_regular_admin(client, console_headers):
    response = await client.post("/api/v1/admin/admins", headers=console_headers, json={
        "username": "peer_owner", "nickname": "同级管理员", "password": "NewPass67890", "role": "owner",
    })
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "owner"
    assert response.json()["data"]["mfa_enabled"] is False

    response = await client.post("/api/v1/admin/admins", headers=console_headers, json={
        "username": "daily_admin", "nickname": "日常管理员", "password": "NewPass67890", "role": "admin",
    })
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"

    response = await client.get("/api/v1/admin/admins", headers=console_headers)
    rows = response.json()["data"]["items"]
    assert all("role" in row and "mfa_enabled" in row for row in rows)


async def test_login_entry_must_match_account_role(client):
    admin = await _ordinary_admin("entry_admin")
    response = await client.post("/api/v1/admin/auth/login", json={
        "username": admin.username, "password": PASSWORD, "login_kind": "owner",
    })
    assert response.status_code == 403
    response = await client.post("/api/v1/admin/auth/login", json={
        "username": admin.username, "password": PASSWORD, "login_kind": "admin",
    })
    assert response.status_code == 200
    assert response.json()["data"]["admin"]["role"] == "admin"


async def test_regular_admin_production_login_needs_only_password(client, monkeypatch):
    admin = await _ordinary_admin("production_admin")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = await client.post("/api/v1/admin/auth/login", json={
        "username": admin.username, "password": PASSWORD, "login_kind": "admin",
    })
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    response = await client.get("/api/v1/admin/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "admin"


async def test_new_owner_enrolls_independent_mfa_before_access(client, console_headers, monkeypatch):
    response = await client.post("/api/v1/admin/admins", headers=console_headers, json={
        "username": "enroll_owner", "nickname": "新超级管理员", "password": "NewPass67890", "role": "owner",
    })
    assert response.status_code == 200
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    login = await client.post("/api/v1/admin/auth/login", json={
        "username": "enroll_owner", "password": "NewPass67890", "login_kind": "owner",
    })
    assert login.status_code == 200
    setup = login.json()["data"]
    assert setup["mfa_setup_required"] is True
    assert "access_token" not in setup
    assert setup["secret"]
    assert setup["otpauth_url"].startswith("otpauth://totp/")

    response = await client.get("/api/v1/admin/runtime-controls", headers=auth_header(setup["setup_token"]))
    assert response.status_code == 403

    code = totp_code(setup["secret"], int(time.time() // 30))
    response = await client.post("/api/v1/admin/auth/mfa/setup", json={
        "setup_token": setup["setup_token"], "totp_code": code,
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["admin"]["mfa_enabled"] is True
    assert data["admin"]["role"] == "owner"

    response = await client.get("/api/v1/admin/runtime-controls", headers=auth_header(data["access_token"]))
    assert response.status_code == 200

    async with TestSession() as db:
        admin = (await db.execute(select(AdminUser)
                                  .where(AdminUser.username == "enroll_owner"))).scalar_one()
        assert admin.mfa_secret_encrypted
        assert admin.mfa_secret_encrypted != setup["secret"]
        log = (await db.execute(select(AdminLog)
                                .where(AdminLog.action == "admin.mfa_setup"))).scalar_one()
        assert log.target_id == str(admin.id)


async def test_owner_with_mfa_rejects_missing_code(client, console_headers, monkeypatch):
    from app.utils.mfa import encrypt_secret
    async with TestSession() as db:
        admin = AdminUser(username="existing_owner", nickname="现有超级管理员", role="owner",
                          password_hash=hash_password(PASSWORD), mfa_secret_encrypted=encrypt_secret("JBSWY3DPEHPK3PXP"))
        db.add(admin)
        await db.commit()
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = await client.post("/api/v1/admin/auth/login", json={
        "username": "existing_owner", "password": PASSWORD, "login_kind": "owner",
    })
    assert response.status_code == 401
