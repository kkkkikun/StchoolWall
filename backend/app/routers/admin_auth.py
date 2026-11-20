"""管理后台认证、超级管理员首次 2FA 绑定和账号管理。"""
import base64
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import AdminActor, require_admin_console, require_admin_owner
from app.schemas.admin_auth import (
    AdminAccountCreateRequest,
    AdminAccountStatusRequest,
    AdminLoginRequest,
    AdminMfaSetupVerifyRequest,
    AdminPasswordChangeRequest,
    AdminPasswordResetRequest,
)
from app.services.admin_auth import (
    MFA_SETUP_SCOPE,
    authenticate_admin,
    change_admin_password,
    create_admin_user,
    get_admin_by_id,
    issue_console_token,
    issue_mfa_setup_token,
    list_admin_users,
    reset_admin_password,
    set_admin_active,
)
from app.services import admin_log
from app.services.admin_log import log_admin_action
from app.utils.mfa import encrypt_secret, verify_totp
from app.utils.rate_limit import LOGIN_USER_RATE, check_rate_limit, clear_rate, get_rate, incr_rate
from app.utils.security import decode_access_token

router = APIRouter()
LOGIN_RATE_MAX = 10
LOGIN_RATE_WINDOW = 60


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _admin_summary(admin) -> dict:
    return {
        "id": str(admin.id), "username": admin.username, "nickname": admin.nickname,
        "role": admin.role, "mfa_enabled": bool(admin.mfa_secret_encrypted),
    }


def _session_data(response: Response, admin, mfa: bool) -> dict:
    admin_token = issue_console_token(admin, mfa=mfa)
    csrf = secrets.token_urlsafe(32)
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        "sw_admin", admin_token, httponly=True, secure=settings.ENVIRONMENT == "production",
        samesite="strict", path="/api/v1/admin", max_age=settings.ADMIN_TOKEN_EXPIRE_HOURS * 3600,
    )
    response.set_cookie(
        "sw_admin_csrf", csrf, secure=settings.ENVIRONMENT == "production",
        samesite="strict", path="/", max_age=settings.ADMIN_TOKEN_EXPIRE_HOURS * 3600,
    )
    return {"access_token": admin_token, "admin": _admin_summary(admin)}


@router.post("/auth/login")
async def admin_login(body: AdminLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """普通管理员密码登录；超级管理员使用独立 TOTP 或完成首次绑定。"""
    ip = _client_ip(request)
    await check_rate_limit(f"rl:admin_login:ip:{ip}", LOGIN_RATE_MAX, LOGIN_RATE_WINDOW)
    username_key = f"rl:admin_login:user:{body.username}"
    max_fails, window = LOGIN_USER_RATE
    if await get_rate(username_key) >= max_fails:
        raise HTTPException(429, "失败次数过多，请稍后再试")

    admin = await authenticate_admin(db, body.username, body.password)
    if admin is None:
        await incr_rate(username_key, window)
        raise HTTPException(401, "用户名或密码错误")
    if body.login_kind is not None and body.login_kind != admin.role:
        raise HTTPException(403, "账号类型与所选登录入口不匹配")

    mfa = False
    if admin.role == "owner" and admin.mfa_secret_encrypted:
        await db.refresh(admin, with_for_update=True)
        counter = verify_totp(admin.mfa_secret_encrypted, body.totp_code or "", admin.mfa_last_counter)
        if counter is None:
            await incr_rate(username_key, window)
            raise HTTPException(401, "用户名、密码或验证码错误")
        admin.mfa_last_counter = counter
        await db.commit()
        mfa = True
    elif admin.role == "owner" and settings.ENVIRONMENT == "production":
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        setup_token = issue_mfa_setup_token(admin, encrypt_secret(secret))
        response.headers["Cache-Control"] = "no-store"
        return {"code": 0, "message": "请绑定超级管理员双重验证", "data": {
            "mfa_setup_required": True,
            "setup_token": setup_token,
            "secret": secret,
            "otpauth_url": f"otpauth://totp/{quote('SchoolWall:' + admin.username)}?secret={secret}&issuer=SchoolWall",
            "admin": _admin_summary(admin),
        }}

    await clear_rate(username_key)
    return {"code": 0, "message": "登录成功", "data": _session_data(response, admin, mfa)}


@router.post("/auth/mfa/setup")
async def verify_mfa_setup(
    body: AdminMfaSetupVerifyRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db),
):
    """验证首次绑定码；setup token 不包含正式后台访问权限。"""
    await check_rate_limit(f"rl:admin_mfa_setup:ip:{_client_ip(request)}", 20, 60)
    payload = decode_access_token(body.setup_token)
    if not payload or payload.get("scope") != MFA_SETUP_SCOPE:
        raise HTTPException(401, "绑定会话无效或已过期，请重新登录")
    encrypted = payload.get("mfa_secret")
    if not isinstance(encrypted, str):
        raise HTTPException(401, "绑定会话无效")
    admin = await get_admin_by_id(db, str(payload.get("sub", "")))
    if not admin or not admin.is_active or admin.role != "owner":
        raise HTTPException(403, "账号不可用")
    if payload.get("pwd_version", 0) != admin.pwd_version:
        raise HTTPException(401, "账号状态已变化，请重新登录")
    if admin.mfa_secret_encrypted:
        raise HTTPException(409, "该账号已绑定双重验证，请直接登录")
    counter = verify_totp(encrypted, body.totp_code, None)
    if counter is None:
        raise HTTPException(401, "验证码错误或已过期")
    admin.mfa_secret_encrypted = encrypted
    admin.mfa_last_counter = counter
    actor = AdminActor(str(admin.id), admin.nickname, "console", admin.role, admin.username)
    await log_admin_action(db, actor, admin_log.ADMIN_MFA_SETUP, target_type="admin_user",
                           target_id=admin.id, ip=_client_ip(request))
    await db.commit()
    await clear_rate(f"rl:admin_login:user:{admin.username}")
    return {"code": 0, "message": "双重验证绑定成功", "data": _session_data(response, admin, True)}


@router.get("/auth/me")
async def admin_me(actor: AdminActor = Depends(require_admin_console)):
    return {"code": 0, "data": {
        "id": actor.id, "display_name": actor.display_name, "source": actor.source,
        "role": actor.role, "username": actor.username,
    }}


@router.put("/auth/password")
async def admin_change_password(
    body: AdminPasswordChangeRequest,
    actor: AdminActor = Depends(require_admin_console),
    db: AsyncSession = Depends(get_db),
):
    """修改密码；成功后 pwd_version+1，所有旧 console token 失效（需重新登录）。"""
    if actor.source != "console":
        raise HTTPException(403, "请使用管理后台账号登录后修改密码")
    admin = await get_admin_by_id(db, actor.id)
    if admin is None:
        raise HTTPException(401, "账号不存在")
    ok = await change_admin_password(db, admin, body.old_password, body.new_password)
    if not ok:
        raise HTTPException(400, "原密码错误")
    return {"code": 0, "message": "密码已修改，请重新登录"}


@router.get("/admins")
async def list_admin_accounts(
    q: str | None = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    items, total = await list_admin_users(db, q=q, page=page, page_size=page_size)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/admins")
async def create_admin_account(
    body: AdminAccountCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_owner),
):
    admin, error = await create_admin_user(db, body.username, body.nickname, body.password, body.role)
    if error:
        raise HTTPException(400, error)
    await log_admin_action(
        db, actor, admin_log.ADMIN_CREATE, target_type="admin_user", target_id=admin.id,
        detail={"username": admin.username, "nickname": admin.nickname, "role": admin.role},
        ip=_client_ip(request),
    )
    await db.commit()
    return {"code": 0, "message": "创建成功", "data": _admin_summary(admin)}


@router.put("/admins/{admin_id}/status")
async def update_admin_account_status(
    admin_id: str,
    body: AdminAccountStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_owner),
):
    admin, error = await set_admin_active(db, admin_id, body.is_active, actor_id=actor.id)
    if error == "管理员不存在":
        raise HTTPException(404, error)
    if error:
        raise HTTPException(400, error)
    await log_admin_action(
        db, actor, admin_log.ADMIN_STATUS, target_type="admin_user", target_id=admin_id,
        detail={"is_active": body.is_active}, ip=_client_ip(request),
    )
    await db.commit()
    return {"code": 0, "message": "已启用" if body.is_active else "已停用",
            "data": {"id": str(admin.id), "is_active": admin.is_active}}


@router.put("/admins/{admin_id}/password")
async def reset_admin_account_password(
    admin_id: str,
    body: AdminPasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_owner),
):
    admin, error = await reset_admin_password(db, admin_id, body.new_password, actor_id=actor.id)
    if error == "管理员不存在":
        raise HTTPException(404, error)
    if error:
        raise HTTPException(400, error)
    await log_admin_action(db, actor, admin_log.ADMIN_PASSWORD_RESET,
                           target_type="admin_user", target_id=admin_id, ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "密码已重置", "data": {"id": str(admin.id)}}


@router.post("/auth/logout")
async def admin_logout(response: Response, actor: AdminActor = Depends(require_admin_console),
                       db: AsyncSession = Depends(get_db)):
    admin = await get_admin_by_id(db, actor.id)
    if admin:
        admin.pwd_version += 1
        await db.commit()
    response.delete_cookie("sw_admin", path="/api/v1/admin")
    response.delete_cookie("sw_admin_csrf", path="/")
    return {"code": 0, "message": "已退出管理后台"}
