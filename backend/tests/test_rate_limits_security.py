"""限流安全测试：写操作按用户限流 / 管理台按用户名退避 / 限流键原子 TTL。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.routers.admin_auth as admin_auth_mod
import app.routers.interaction as interaction_mod
import app.routers.posts as posts_mod
import app.routers.upload as upload_mod
from app.models.post import Post
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _tighten(monkeypatch, n=2):
    """把各路由阈值压到 n 次，测试不必打满真实配额。"""
    monkeypatch.setattr(posts_mod, "RATE_POST_CREATE", (n, 600))
    monkeypatch.setattr(interaction_mod, "RATE_COMMENT", (n, 600))
    monkeypatch.setattr(posts_mod, "RATE_REPORT", (n, 600))
    monkeypatch.setattr(upload_mod, "RATE_UPLOAD", (n, 600))
    monkeypatch.setattr(admin_auth_mod, "LOGIN_USER_RATE", (n, 600))


async def _seed_post(user_id, status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content="限流测试帖", images=[], status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


class TestUserRateLimits:

    async def test_post_creation_limited(self, client, student_user, monkeypatch):
        _tighten(monkeypatch, 2)
        headers = auth_header(_token(student_user))
        for _ in range(2):
            r = await client.post("/api/v1/posts",
                                  json={"post_type": "general", "content": "帖"},
                                  headers=headers)
            assert r.status_code == 200
        r3 = await client.post("/api/v1/posts",
                               json={"post_type": "general", "content": "第三帖"},
                               headers=headers)
        assert r3.status_code == 429

    async def test_comment_limited(self, client, student_user, monkeypatch):
        _tighten(monkeypatch, 2)
        pid = await _seed_post(student_user.id)
        headers = auth_header(_token(student_user))
        for _ in range(2):
            r = await client.post(f"/api/v1/posts/{pid}/comments",
                                  json={"content": "评论"}, headers=headers)
            assert r.status_code == 200
        r3 = await client.post(f"/api/v1/posts/{pid}/comments",
                               json={"content": "第三条"}, headers=headers)
        assert r3.status_code == 429

    async def test_report_limited(self, client, student_user, admin_user, monkeypatch):
        _tighten(monkeypatch, 2)
        pid = await _seed_post(admin_user.id)
        headers = auth_header(_token(student_user))
        for _ in range(2):
            r = await client.post(f"/api/v1/posts/{pid}/report",
                                  json={"reason": "spam"}, headers=headers)
            assert r.status_code == 200
        r3 = await client.post(f"/api/v1/posts/{pid}/report",
                               json={"reason": "spam"}, headers=headers)
        assert r3.status_code == 429

    async def test_upload_limited(self, client, student_user, monkeypatch):
        import io
        _tighten(monkeypatch, 2)
        headers = auth_header(_token(student_user))
        from PIL import Image
        output = io.BytesIO()
        Image.new("RGB", (16, 16)).save(output, format="JPEG")
        files = {"file": ("a.jpg", output.getvalue(), "image/jpeg")}
        for _ in range(2):
            r = await client.post("/api/v1/upload/direct?kind=posts", files=files, headers=headers)
            assert r.status_code == 200
        r3 = await client.post("/api/v1/upload/direct?kind=posts", files=files, headers=headers)
        assert r3.status_code == 429

    async def test_limits_are_per_user(self, client, student_user, admin_user, monkeypatch):
        """A 触发限流不影响 B。"""
        _tighten(monkeypatch, 2)
        headers_a = auth_header(_token(student_user))
        for _ in range(2):
            await client.post("/api/v1/posts", json={"post_type": "general", "content": "A"},
                              headers=headers_a)
        r_b = await client.post("/api/v1/posts", json={"post_type": "general", "content": "B"},
                                headers=auth_header(_token(admin_user)))
        assert r_b.status_code == 200


class TestAdminLoginBackoff:

    async def test_username_lockout(self, client, console_admin, monkeypatch):
        """同一用户名连续失败超阈值 → 正确密码也 429；成功后计数清零。"""
        _tighten(monkeypatch, 2)
        wrong = {"username": console_admin.username, "password": "WrongPass123"}
        for _ in range(2):
            r = await client.post("/api/v1/admin/auth/login", json=wrong)
            assert r.status_code == 401
        r_lock = await client.post("/api/v1/admin/auth/login", json={
            "username": console_admin.username, "password": "Admin12345",
        })
        assert r_lock.status_code == 429

    async def test_success_resets_counter(self, client, console_admin, monkeypatch):
        _tighten(monkeypatch, 2)
        wrong = {"username": console_admin.username, "password": "WrongPass123"}
        await client.post("/api/v1/admin/auth/login", json=wrong)  # 1 次失败
        r_ok = await client.post("/api/v1/admin/auth/login", json={
            "username": console_admin.username, "password": "Admin12345",
        })
        assert r_ok.status_code == 200  # 成功清零
        r_fail = await client.post("/api/v1/admin/auth/login", json=wrong)
        assert r_fail.status_code == 401  # 重新计数


class TestRateKeyAtomicity:

    async def test_counter_key_has_ttl_from_first_hit(self):
        """SET NX：首个请求即建立带 TTL 的键，无"永久限流键"窗口。"""
        from app.utils import rate_limit as rl
        key = "rl:test:ttl_probe"
        try:
            await rl.check_rate_limit(key, 100, 600)
            ttl = await rl.redis_client.ttl(key)
            assert ttl > 0
        finally:
            await rl.redis_client.delete(key)
