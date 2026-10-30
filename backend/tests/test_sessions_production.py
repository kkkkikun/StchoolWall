"""Production account and administrator boundaries, using real PostgreSQL transactions."""
import asyncio
from datetime import timedelta
import uuid

import pytest
from fastapi import HTTPException
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app.config import settings
from app.models.session import LoginIdentity, RecoveryCode, SpentRefreshToken, UserSession
from app.models.admin_user import AdminUser
from app.models.job import Job
from app.models.post import Post
from app.models.admin_log import AdminLog
from app.services.sessions import issue_session, now_utc, refresh_session, token_hash
from app.utils.security import create_access_token
from app.utils.mfa import encrypt_secret, decrypt_secret, verify_totp
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio
PASSWORD = "Long-test-password-492!"

async def register(client, username="student001", platform="native"):
    response = await client.post("/api/v1/auth/register", json={"username": username, "password": PASSWORD},
                                 headers={"X-Client-Type": platform})
    assert response.status_code == 200, response.text
    return response.json()["data"]

async def test_registration_is_explicit_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    result = await client.post("/api/v1/auth/web-login", json={"username": "newuser", "password": PASSWORD})
    assert result.status_code == 401
    async with TestSession() as db:
        assert await db.scalar(select(func.count()).select_from(LoginIdentity)) == 0

async def test_short_access_and_refresh_hash_only(client):
    data = await register(client)
    assert data["expires_in"] <= 900
    async with TestSession() as db:
        session = await db.get(UserSession, uuid.UUID(data["session_id"]))
        assert session.refresh_hash == token_hash(data["refresh_token"])
        assert data["refresh_token"] != session.refresh_hash

async def test_all_rotated_refresh_replays_revoke_sessions(client):
    data = await register(client)
    second = await client.post("/api/v1/auth/web-login", json={"username":"student001","password":PASSWORD})
    refresh = data["refresh_token"]
    for _ in range(3):
        result = await client.post("/api/v1/auth/refresh", json={"refresh_token":refresh})
        assert result.status_code == 200
        refresh = result.json()["data"]["refresh_token"]
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token":data["refresh_token"]})
    assert replay.status_code == 401
    invalidated = await client.get("/api/v1/auth/sessions", headers=auth_header(second.json()["data"]["access_token"]))
    assert invalidated.status_code == 401
    async with TestSession() as db:
        assert await db.scalar(select(func.count()).select_from(SpentRefreshToken)) == 3

async def test_concurrent_refresh_accepts_once_then_revokes_replay(guest_user):
    async with TestSession() as db:
        first = await issue_session(db, guest_user)
    async def refresh_one():
        async with TestSession() as db:
            try:
                await refresh_session(db, first["refresh_token"])
                return 200
            except HTTPException as exc:
                return exc.status_code
    results = await asyncio.gather(refresh_one(), refresh_one())
    assert sorted(results) == [200, 401]
    async with TestSession() as db:
        assert (await db.get(UserSession, uuid.UUID(first["session_id"]))).revoked_at

async def test_web_refresh_cookie_is_httponly_and_csrf_checked(client):
    data = await register(client, platform="web")
    assert "refresh_token" not in data
    cookie = next(cookie for cookie in client.cookies.jar if cookie.name == "sw_refresh")
    assert cookie.has_nonstandard_attr("HttpOnly")
    result = await client.post("/api/v1/auth/refresh", json={}, headers={"X-Client-Type":"web"})
    assert result.status_code == 403
    result = await client.post("/api/v1/auth/refresh", json={}, headers={
        "X-Client-Type":"web", "Origin":settings.CORS_ORIGINS.split(",")[0], "X-CSRF-Token":data["csrf_token"]})
    assert result.status_code == 200
    assert "refresh_token" not in result.json()["data"]

async def test_logout_revokes_access_and_refresh(client):
    data = await register(client)
    headers = auth_header(data["access_token"])
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 200
    assert (await client.get("/api/v1/auth/sessions", headers=headers)).status_code == 401
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token":data["refresh_token"]})).status_code == 401

async def test_password_change_revokes_every_device(client):
    data = await register(client)
    second = await client.post("/api/v1/auth/web-login", json={"username":"student001","password":PASSWORD})
    result = await client.put("/api/v1/user/password", headers=auth_header(data["access_token"]),
                              json={"old_password":PASSWORD,"new_password":"Different-password-123"})
    assert result.status_code == 200, result.text
    for token in (data["access_token"], second.json()["data"]["access_token"]):
        assert (await client.get("/api/v1/auth/sessions", headers=auth_header(token))).status_code == 401
    assert (await client.post("/api/v1/auth/web-login", json={"username":"student001","password":PASSWORD})).status_code == 401

async def test_recovery_codes_are_single_use_and_revoke_devices(client):
    data = await register(client)
    result = await client.post("/api/v1/auth/recovery-codes", headers=auth_header(data["access_token"]))
    assert result.status_code == 200
    code = result.json()["data"]["codes"][0]
    async with TestSession() as db:
        assert (await db.scalar(select(RecoveryCode).where(RecoveryCode.code_hash == token_hash(code)))).code_hash != code
    payload = {"username":"student001","recovery_code":code,"new_password":"Recovered-password-123"}
    assert (await client.post("/api/v1/auth/recover", json=payload)).status_code == 200
    assert (await client.get("/api/v1/auth/sessions", headers=auth_header(data["access_token"]))).status_code == 401
    assert (await client.post("/api/v1/auth/recover", json=payload)).status_code == 401

async def test_pairing_preserves_canonical_user_without_implicit_merge(client):
    canonical = await register(client, "canonical")
    fresh = await register(client, "freshaccount")
    code = (await client.post("/api/v1/auth/pairing", headers=auth_header(canonical["access_token"]))).json()["data"]["code"]
    # Two password identities may never overwrite one another.
    result = await client.post("/api/v1/auth/pairing/claim", headers=auth_header(fresh["access_token"]), json={"code":code})
    assert result.status_code == 409

async def test_pairing_wechat_identity_is_explicit_single_use(client, guest_user):
    canonical = await register(client)
    async with TestSession() as db:
        identity = LoginIdentity(user_id=guest_user.id, provider="weixin:test", subject="openid-safe")
        db.add(identity)
        await db.flush()
        fresh = await issue_session(db, guest_user, identity)
    code = (await client.post("/api/v1/auth/pairing", headers=auth_header(canonical["access_token"]))).json()["data"]["code"]
    result = await client.post("/api/v1/auth/pairing/claim", headers=auth_header(fresh["access_token"]), json={"code":code})
    assert result.status_code == 200, result.text
    assert result.json()["data"]["user_info"]["id"] == canonical["user_info"]["id"]
    assert (await client.get("/api/v1/auth/sessions", headers=auth_header(fresh["access_token"]))).status_code == 403
    async with TestSession() as db:
        assert (await db.scalar(select(LoginIdentity).where(LoginIdentity.subject=="openid-safe"))).user_id == uuid.UUID(canonical["user_info"]["id"])

async def test_production_rejects_legacy_user_admin_token(client, admin_token, monkeypatch):
    monkeypatch.setattr(settings,"ENVIRONMENT","production")
    assert (await client.get("/api/v1/admin/stats", headers=auth_header(admin_token))).status_code == 403
    assert (await client.get("/api/v1/auth/sessions", headers=auth_header(admin_token))).status_code == 401

async def test_production_console_requires_mfa(client, console_headers, monkeypatch):
    monkeypatch.setattr(settings,"ENVIRONMENT","production")
    assert (await client.get("/api/v1/admin/stats", headers=console_headers)).status_code == 403

async def test_mfa_encrypted_at_rest_and_counter_replay_fenced(monkeypatch):
    monkeypatch.setattr(settings,"ADMIN_MFA_ENCRYPTION_KEY",Fernet.generate_key().decode())
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    encrypted = encrypt_secret(secret)
    assert encrypted != secret and decrypt_secret(encrypted) == secret
    monkeypatch.setattr("app.utils.mfa.time.time", lambda: 59)
    assert verify_totp(encrypted, "287082", None) == 1
    assert verify_totp(encrypted, "287082", 1) is None

async def test_validation_never_reflects_password(client):
    secret = "x" * 100
    result = await client.post("/api/v1/auth/register", json={"username":"x","password":secret})
    assert result.status_code == 422
    assert secret not in result.text
    assert result.json()["request_id"] == result.headers["x-request-id"]

async def test_retired_academic_password_endpoint(client):
    result = await client.post("/api/v1/auth/verify", json={"password":"never-parse-this"})
    assert result.status_code == 410
    assert "never-parse-this" not in result.text

async def test_manual_post_decision_fences_old_jobs_and_is_audited(client, student_user, console_headers):
    async with TestSession() as db:
        post = Post(user_id=student_user.id, content="人工待审内容", post_type="normal", category="日常", status=0)
        db.add(post)
        await db.flush()
        job = Job(kind="moderate_post",payload={"post_id":post.id},dedupe_key="manual:test",status="review")
        db.add(job)
        await db.commit()
        job_id, post_id = job.id, post.id
    result = await client.post(f"/api/v1/admin/moderation-jobs/{job_id}/review",
        headers=console_headers,json={"decision":"approve","reason":"核对文字图片通过"})
    assert result.status_code == 200, result.text
    again = await client.post(f"/api/v1/admin/moderation-jobs/{job_id}/review",
        headers=console_headers,json={"decision":"reject","reason":"旧页面重复提交"})
    assert again.status_code == 409
    async with TestSession() as db:
        assert (await db.get(Post,post_id)).status == 1
        assert await db.scalar(select(func.count()).select_from(AdminLog).where(AdminLog.action=="moderation.review")) == 1

async def test_appeals_are_private_and_accepting_does_not_publish(client, student_user, student_token, guest_token, console_headers):
    async with TestSession() as db:
        post = Post(user_id=student_user.id,content="被拒绝内容",post_type="normal",category="日常",status=-1)
        db.add(post); await db.commit(); post_id = post.id
    payload = {"entity_type":"post","entity_id":str(post_id),"reason":"请核对完整语境并复查"}
    assert (await client.post("/api/v1/appeals",headers=auth_header(guest_token),json=payload)).status_code == 404
    result = await client.post("/api/v1/appeals",headers=auth_header(student_token),json=payload)
    assert result.status_code == 200
    assert (await client.post("/api/v1/appeals",headers=auth_header(student_token),json=payload)).status_code == 409
    result = await client.post(f'/api/v1/admin/appeals/{result.json()["data"]["id"]}/decision',
        headers=console_headers,json={"decision":"accepted","reason":"已接受复查请前往内容页处理"})
    assert result.status_code == 200
    async with TestSession() as db:
        assert (await db.get(Post,post_id)).status == -1

async def test_duplicate_registration_returns_http_conflict(client):
    await register(client)
    result = await client.post("/api/v1/auth/register", json={"username":"student001","password":PASSWORD})
    assert result.status_code == 409

async def test_publish_switch_leaves_reads_and_logout_available(client, console_headers):
    data = await register(client)
    result = await client.put("/api/v1/admin/runtime-controls",
        headers=console_headers,json={"publishing_enabled":False})
    assert result.status_code == 200
    denied = await client.post("/api/v1/posts",headers=auth_header(data["access_token"]),
                              json={"post_type":"general","content":"暂停期间投稿"})
    assert denied.status_code == 503
    assert (await client.get("/api/v1/posts")).status_code == 200
    assert (await client.post("/api/v1/auth/logout",headers=auth_header(data["access_token"]))).status_code == 200

async def test_pairing_creation_requires_recent_login_and_revocation_cancels_codes(client):
    from app.models.session import PairingCode
    data = await register(client)
    token = auth_header(data["access_token"])
    result = await client.post("/api/v1/auth/pairing",headers=token)
    assert result.status_code == 200
    async with TestSession() as db:
        session = await db.get(UserSession,uuid.UUID(data["session_id"]))
        session.created_at = now_utc() - timedelta(minutes=6)
        await db.commit()
    assert (await client.post("/api/v1/auth/pairing",headers=token)).status_code == 403
    await client.post("/api/v1/auth/sessions/revoke-all",headers=token)
    async with TestSession() as db:
        assert (await db.scalar(select(PairingCode))).used_at is not None

# ---- console 专用令牌失效与 Cookie-CSRF 防线（真实 console-scope token，非 legacy 用户管理员通道） ----

async def test_console_token_dies_after_password_version_bump(client, console_admin, console_headers):
    """改密（pwd_version 递增）后旧 console token 必须立即失效（dependencies.require_admin_console）。"""
    assert (await client.get("/api/v1/admin/stats", headers=console_headers)).status_code == 200
    async with TestSession() as db:
        admin = await db.get(AdminUser, console_admin.id)
        admin.pwd_version += 1
        await db.commit()
    result = await client.get("/api/v1/admin/stats", headers=console_headers)
    assert result.status_code == 401


async def test_admin_cookie_write_without_csrf_is_forbidden(client, console_token):
    """sw_admin Cookie 通道的写请求：缺 CSRF Cookie 或缺匹配 x-csrf-token 头均为 403。"""
    client.cookies.set("sw_admin", console_token)
    # 完全没有 CSRF 对
    result = await client.put("/api/v1/admin/runtime-controls", json={"publishing_enabled": True})
    assert result.status_code == 403
    # 有 CSRF Cookie 但无匹配请求头
    client.cookies.set("sw_admin_csrf", "csrf-test-value")
    result = await client.put("/api/v1/admin/runtime-controls", json={"publishing_enabled": True},
                              headers={"Origin": settings.CORS_ORIGINS.split(",")[0]})
    assert result.status_code == 403


async def test_admin_cookie_write_with_foreign_origin_is_forbidden(client, console_token):
    """CSRF Cookie 与请求头匹配，但 Origin 不在 CORS_ORIGINS 白名单时仍必须 403。"""
    client.cookies.set("sw_admin", console_token)
    client.cookies.set("sw_admin_csrf", "csrf-test-value")
    result = await client.put("/api/v1/admin/runtime-controls", json={"publishing_enabled": True},
                              headers={"x-csrf-token": "csrf-test-value", "Origin": "https://evil.example.com"})
    assert result.status_code == 403
    # 对照组：CSRF 匹配 + 白名单 Origin 时能通过安全依赖（证明上面的 403 来自安全闸而非请求校验）
    ok = await client.put("/api/v1/admin/runtime-controls", json={"publishing_enabled": True},
                          headers={"x-csrf-token": "csrf-test-value",
                                   "Origin": settings.CORS_ORIGINS.split(",")[0]})
    assert ok.status_code == 200
