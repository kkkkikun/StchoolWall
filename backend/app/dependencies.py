import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.user import User
from app.services.sessions import validate_session
from app.utils.security import decode_access_token

bearer_scheme = HTTPBearer()
bearer_scheme_optional = HTTPBearer(auto_error=False)
CONSOLE_SCOPE = "admin_console"

@dataclass
class AdminActor:
    id: str
    display_name: str
    source: str
    role: str = "owner"

async def _resolve_user(token: str, db: AsyncSession) -> User:
    payload = decode_access_token(token)
    if not payload or payload.get("scope") not in {None, "user"}:
        raise HTTPException(401, "Token 无效或已过期")
    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(401, "Token 缺少用户标识") from None
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "用户不存在")
    if user.status != 1:
        raise HTTPException(403, "账号已被冻结或已注销")
    await validate_session(db, user, payload)
    if user.verified_until and user.verified_until <= datetime.now(timezone.utc):
        user.is_verified = False
        if user.role == "student":
            user.role = "guest"
        await db.commit()
    return user

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _resolve_user(credentials.credentials, db)

async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return await _resolve_user(credentials.credentials, db)
    except HTTPException as exc:
        if exc.status_code in {401, 403}:
            return None
        raise

def require_role(*roles: str):
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "权限不足")
        return user
    return _check

async def require_admin_console(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> AdminActor:
    raw = credentials.credentials if credentials else request.cookies.get("sw_admin")
    if not raw:
        raise HTTPException(401, "请登录管理后台")
    if not credentials and request.method not in {"GET", "HEAD", "OPTIONS"}:
        import secrets
        csrf = request.cookies.get("sw_admin_csrf", "")
        allowed = {o.strip() for o in settings.CORS_ORIGINS.split(",")}
        if not csrf or not secrets.compare_digest(csrf, request.headers.get("x-csrf-token", "")) or request.headers.get("origin") not in allowed:
            raise HTTPException(403, "请求来源验证失败")
    payload = decode_access_token(raw)
    if not payload:
        raise HTTPException(401, "Token 无效或已过期")
    if payload.get("scope") == CONSOLE_SCOPE:
        try:
            admin_id = uuid.UUID(payload.get("sub", ""))
        except (ValueError, TypeError):
            raise HTTPException(401, "Token 无效") from None
        admin = await db.get(AdminUser, admin_id)
        if not admin:
            raise HTTPException(401, "管理员账号不存在")
        if not admin.is_active:
            raise HTTPException(403, "管理员账号已停用")
        if payload.get("pwd_version", 0) != admin.pwd_version:
            raise HTTPException(401, "密码已变更，请重新登录")
        if settings.ENVIRONMENT == "production" and (not admin.mfa_secret_encrypted or not payload.get("mfa")):
            raise HTTPException(403, "请使用双重验证登录管理后台")
        return AdminActor(str(admin.id), admin.nickname, "console")
    # Isolated legacy test fixtures do not authorize any deployed API.
    if settings.ENVIRONMENT == "test":
        user = await _resolve_user(credentials.credentials, db)
        if user.role == "admin":
            return AdminActor(str(user.id), user.nickname, "legacy")
        raise HTTPException(403, "权限不足")
    raise HTTPException(403, "请使用独立管理后台账号登录")
