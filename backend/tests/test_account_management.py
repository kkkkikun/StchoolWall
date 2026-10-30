"""账号管理测试：网页账号修改密码 / 注销账号。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from app.utils.password import hash_password
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _mk_web_user(username: str = "webuser", password: str = "OldPass123", **kwargs) -> User:
    async with TestSession() as db:
        u = User(
            openid=f"web:{username}",
            nickname=username,
            role="student",
            is_verified=True,
            web_password_hash=hash_password(password),
            **kwargs,
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_change_password_success(self, client: AsyncClient):
        u = await _mk_web_user("chgpass")
        token = create_access_token({"sub": str(u.id), "role": u.role})

        r = await client.put(
            "/api/v1/user/password",
            json={"old_password": "OldPass123", "new_password": "NewPass456!"},
            headers=auth_header(token),
        )
        assert r.status_code == 200

        # 新密码可登录，旧密码 401
        ok = await client.post("/api/v1/auth/web-login", json={"username": "chgpass", "password": "NewPass456!"})
        assert ok.status_code == 200
        bad = await client.post("/api/v1/auth/web-login", json={"username": "chgpass", "password": "OldPass123"})
        assert bad.status_code == 401

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, client: AsyncClient):
        u = await _mk_web_user("wrongold")
        token = create_access_token({"sub": str(u.id), "role": u.role})
        r = await client.put(
            "/api/v1/user/password",
            json={"old_password": "NotRight1", "new_password": "NewPass456!"},
            headers=auth_header(token),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_change_password_no_web_password(self, client: AsyncClient, student_user: User):
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/user/password",
            json={"old_password": "whatever1", "new_password": "whatever2-long"},
            headers=auth_header(token),
        )
        assert r.status_code == 400


class TestDeleteAccount:
    @pytest.mark.asyncio
    async def test_deactivate_with_password(self, client: AsyncClient):
        u = await _mk_web_user("deluser", real_name="真名", student_id="20240099", wechat_id="wx_del")
        token = create_access_token({"sub": str(u.id), "role": u.role})

        r = await client.post(
            "/api/v1/user/account/deactivate",
            json={"password": "OldPass123"},
            headers=auth_header(token),
        )
        assert r.status_code == 200

        async with TestSession() as db:
            row = (await db.execute(select(User).where(User.id == u.id))).scalar_one()
            assert row.status == -2
            assert row.nickname == "已注销用户"
            assert row.real_name is None
            assert row.student_id is None
            assert row.wechat_id is None
            assert row.web_password_hash is None

        # 注销后 token 失效
        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r2.status_code == 403

        # 身份数据已清除。开发自动注册也只能得到新UUID/游客，不能恢复旧账号。
        r3 = await client.post("/api/v1/auth/web-login", json={"username": "deluser", "password": "OldPass123"})
        assert r3.status_code == 200
        assert r3.json()["data"]["user_info"]["id"] != str(u.id)
        assert r3.json()["data"]["role"] == "guest"

    @pytest.mark.asyncio
    async def test_deactivate_wrong_password(self, client: AsyncClient):
        u = await _mk_web_user("delwrong")
        token = create_access_token({"sub": str(u.id), "role": u.role})
        r = await client.post(
            "/api/v1/user/account/deactivate",
            json={"password": "WrongPass1"},
            headers=auth_header(token),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_deactivate_wechat_user_without_password(self, client: AsyncClient, student_user: User):
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(
            "/api/v1/user/account/deactivate",
            json={"password": None},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        r2 = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert r2.status_code == 403
