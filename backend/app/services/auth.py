import random
import string
import uuid

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.session import LoginIdentity
from app.models.user import User
from app.services.sessions import issue_session
from app.utils.password import hash_password, verify_password


def _generate_nickname() -> str:
    return "校园同学_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def _identity(db, provider: str, subject: str, legacy_openid: str):
    identity = (await db.execute(select(LoginIdentity).where(
        LoginIdentity.provider == provider, LoginIdentity.subject == subject))).scalar_one_or_none()
    if identity:
        return identity, await db.get(User, identity.user_id)
    user = (await db.execute(select(User).where(User.openid == legacy_openid))).scalar_one_or_none()
    if user:
        identity = LoginIdentity(user_id=user.id, provider=provider, subject=subject,
                                 password_hash=user.web_password_hash if provider == "password" else None)
        db.add(identity)
        await db.flush()
    return identity, user


async def _login_result(db, user, identity, client_type="native"):
    if user.status != 1:
        return {"code": 403, "message": "账号已被冻结或已注销", "data": None}
    return {"code": 0, "message": "success", "data": await issue_session(db, user, identity, client_type)}


async def _wechat_identity(db, provider, subject, legacy_openid, client_type):
    identity, user = await _identity(db, provider, subject, legacy_openid)
    if user is None:
        user = User(openid=legacy_openid, nickname=_generate_nickname(), role="guest", is_verified=False)
        db.add(user)
        await db.flush()
        identity = LoginIdentity(user_id=user.id, provider=provider, subject=subject)
        db.add(identity)
        await db.flush()
    return await _login_result(db, user, identity, client_type)


async def wx_login(code: str, db: AsyncSession, client_type="weixin") -> dict:
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            response = await client.get("https://api.weixin.qq.com/sns/jscode2session", params={
                "appid": settings.WECHAT_APP_ID, "secret": settings.WECHAT_APP_SECRET,
                "js_code": code, "grant_type": "authorization_code"})
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return {"code": 503, "message": "微信登录服务暂时不可用，请稍后重试", "data": None}
    if not data.get("openid"):
        return {"code": 400, "message": "微信登录失败，请重试", "data": None}
    return await _wechat_identity(db, "weixin:" + settings.WECHAT_APP_ID, data["openid"],
                                  data["openid"], client_type)


async def mp_oauth_login(db: AsyncSession, code: str, client_type="web") -> dict:
    if not settings.WECHAT_MP_APP_ID or not settings.WECHAT_MP_APP_SECRET:
        return {"code": 400, "message": "公众号登录未配置，请联系管理员", "data": None}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            response = await client.get("https://api.weixin.qq.com/sns/oauth2/access_token", params={
                "appid": settings.WECHAT_MP_APP_ID, "secret": settings.WECHAT_MP_APP_SECRET,
                "code": code, "grant_type": "authorization_code"})
            data = response.json()
    except (httpx.HTTPError, ValueError):
        return {"code": 503, "message": "微信授权服务暂时不可用，请重试", "data": None}
    if not data.get("openid"):
        return {"code": 400, "message": "微信授权失败，请重试", "data": None}
    return await _wechat_identity(db, "mp:" + settings.WECHAT_MP_APP_ID, data["openid"],
                                  "mp:" + data["openid"], client_type)


async def dev_login(db: AsyncSession, as_admin=False) -> dict:
    openid = "dev_demo_admin" if as_admin else "dev_demo_student"
    user = (await db.execute(select(User).where(User.openid == openid))).scalar_one_or_none()
    if user is None:
        user = User(openid=openid, nickname="演示管理员" if as_admin else "演示同学",
                    role="admin" if as_admin else "student", is_verified=True)
        db.add(user)
        await db.flush()
    return await _login_result(db, user, None)


async def student_verify(user, student_id, password, db):
    return {"code": 410, "message": "教务密码认证已停用，请使用学生证人工核验", "data": None}


async def web_login(db: AsyncSession, username: str, password: str, client_type="native",
                    register: bool | None = None) -> dict:
    identity, user = await _identity(db, "password", username, "web:" + username)
    if user is None:
        if register is False or (register is None and settings.ENVIRONMENT == "production"):
            verify_password(password, "$2b$12$C6UzMDM.H6dfI/f/IKcEe.uoC5m.zZC6xvFX9Vv3Xb.vJxJ9QfQuG")
            return {"code": 401, "message": "用户名或密码错误", "data": None}
        user = User(openid="web:" + username, nickname=_generate_nickname(), role="guest", is_verified=False,
                    web_password_hash=hash_password(password))
        db.add(user)
        await db.flush()
        identity = LoginIdentity(user_id=user.id, provider="password", subject=username,
                                 password_hash=user.web_password_hash)
        db.add(identity)
        await db.flush()
    elif register is True:
        raise HTTPException(409, "该登录名不可用")
    elif not identity.password_hash or not verify_password(password, identity.password_hash):
        return {"code": 401, "message": "用户名或密码错误", "data": None}
    return await _login_result(db, user, identity, client_type)
