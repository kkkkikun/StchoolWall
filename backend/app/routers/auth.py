import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import bearer_scheme, get_current_user
from app.models.post import Post
from app.models.session import LoginIdentity, PairingCode, UserSession
from app.models.user import User
from app.schemas.auth import MpLoginRequest, WebLoginRequest, WxLoginRequest
from app.services.auth import dev_login, mp_oauth_login, web_login, wx_login
from app.services.sessions import issue_session, now_utc, refresh_session, revoke_user_sessions, token_hash
from app.services.runtime_controls import require_registration
from app.utils.password import hash_password
from app.utils.rate_limit import LOGIN_USER_RATE, check_rate_limit, clear_rate, get_rate, incr_rate
from app.utils.security import decode_access_token

router = APIRouter()
WEB_LOGIN_IP_RATE = (60, 60)
WEB_LOGIN_USER_RATE = LOGIN_USER_RATE


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(None, min_length=30, max_length=200)


class PairClaim(BaseModel):
    code: str = Field(..., min_length=8, max_length=32)


class RegisterRequest(WebLoginRequest):
    password: str = Field(..., min_length=10, max_length=64)


class SetPasswordRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=10, max_length=64)


def _client(request):
    return request.headers.get("x-client-type", "native") if request.headers.get("x-client-type", "native") in {
        "web", "android", "weixin", "native"} else "native"


def _respond(result, request, response):
    if isinstance(result.get("code"), int) and 400 <= result["code"] < 600:
        raise HTTPException(result["code"], result.get("message", "登录失败"))
    data = result.get("data")
    if data and _client(request) == "web":
        csrf = secrets.token_urlsafe(32)
        response.set_cookie("sw_refresh", data.pop("refresh_token"), httponly=True,
            secure=settings.ENVIRONMENT == "production", samesite="lax", path="/api/v1/auth",
            max_age=settings.REFRESH_EXPIRE_DAYS * 86400)
        response.set_cookie("sw_csrf", csrf, secure=settings.ENVIRONMENT == "production",
            samesite="lax", path="/", max_age=settings.REFRESH_EXPIRE_DAYS * 86400)
        data["csrf_token"] = csrf
    response.headers["Cache-Control"] = "no-store"
    return result


async def _ip_rate(request, name, limit=60):
    ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"rl:{name}:ip:{ip}", limit, 60)


@router.post("/login")
async def login(body: WxLoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await _ip_rate(request, "wx_login")
    try:
        result = await wx_login(body.code, db, _client(request))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "登录状态发生变化，请重试") from None
    return _respond(result, request, response)


@router.post("/mp-login")
async def mp_login_route(body: MpLoginRequest, request: Request, response: Response,
                         db: AsyncSession = Depends(get_db)):
    await _ip_rate(request, "mp_login")
    try:
        result = await mp_oauth_login(db, body.code, _client(request))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "登录状态发生变化，请重试") from None
    return _respond(result, request, response)


@router.post("/dev-login")
async def dev_login_route(request: Request, response: Response, as_admin: bool = Query(False),
                          db: AsyncSession = Depends(get_db)):
    if not (settings.ENVIRONMENT == "development" and settings.DEV_LOGIN_ENABLED):
        raise HTTPException(404, "Not Found")
    return _respond(await dev_login(db, as_admin), request, response)


@router.post("/web-login")
async def web_login_route(body: WebLoginRequest, request: Request, response: Response,
                          db: AsyncSession = Depends(get_db)):
    await _ip_rate(request, "web_login")
    key = "rl:web_login:user:" + token_hash(body.username)
    if await get_rate(key) >= WEB_LOGIN_USER_RATE[0]:
        raise HTTPException(429, "失败次数过多，请稍后再试")
    try:
        result = await web_login(db, body.username, body.password, _client(request))
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "登录状态发生变化，请重试") from None
    if result.get("code") == 401:
        await incr_rate(key, WEB_LOGIN_USER_RATE[1])
    else:
        await clear_rate(key)
    return _respond(result, request, response)


@router.post("/register", dependencies=[Depends(require_registration)])
async def register(body: RegisterRequest, request: Request, response: Response,
                   db: AsyncSession = Depends(get_db)):
    await _ip_rate(request, "register", 10)
    try:
        result = await web_login(db, body.username, body.password, _client(request), register=True)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "该登录名不可用") from None
    return _respond(result, request, response)


@router.post("/verify")
async def retired_verification():
    # No request model: deprecated academic passwords are never parsed or reflected.
    raise HTTPException(410, "教务密码认证已停用，请使用学生证人工核验")


def _cookie_refresh(request, body):
    if body.refresh_token:
        return body.refresh_token
    raw = request.cookies.get("sw_refresh")
    csrf = request.cookies.get("sw_csrf", "")
    header = request.headers.get("x-csrf-token", "")
    origin = request.headers.get("origin")
    allowed = {o.strip() for o in settings.CORS_ORIGINS.split(",")}
    if (not raw or not csrf or not secrets.compare_digest(csrf, header) or
            not origin or origin not in allowed):
        raise HTTPException(403, "请求来源验证失败")
    return raw


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request, response: Response,
                  db: AsyncSession = Depends(get_db)):
    await _ip_rate(request, "refresh", 120)
    result = {"code": 0, "data": await refresh_session(db, _cookie_refresh(request, body))}
    return _respond(result, request, response)


@router.post("/logout")
async def logout(request: Request, response: Response, user: User = Depends(get_current_user),
                 credentials=Depends(bearer_scheme), db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(credentials.credentials) or {}
    if payload.get("sid"):
        await db.execute(update(UserSession).where(UserSession.id == uuid.UUID(payload["sid"]),
            UserSession.user_id == user.id).values(revoked_at=now_utc()))
        await db.commit()
    await db.execute(update(PairingCode).where(PairingCode.user_id == user.id,
        PairingCode.used_at.is_(None)).values(used_at=now_utc()))
    await db.commit()
    response.delete_cookie("sw_refresh", path="/api/v1/auth")
    response.delete_cookie("sw_csrf", path="/")
    return {"code": 0, "message": "已退出登录"}


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(UserSession).where(UserSession.user_id == user.id,
        UserSession.revoked_at.is_(None), UserSession.expires_at > now_utc())
        .order_by(UserSession.created_at.desc()).limit(50))).scalars()
    return {"code": 0, "data": {"items": [{"id": str(s.id), "client_type": s.client_type,
        "created_at": s.created_at.isoformat(), "last_seen_at": s.last_seen_at.isoformat()} for s in rows]}}


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: uuid.UUID, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    await db.execute(update(PairingCode).where(PairingCode.user_id == user.id,
        PairingCode.used_at.is_(None)).values(used_at=now_utc()))
    await db.execute(update(UserSession).where(UserSession.id == session_id,
        UserSession.user_id == user.id).values(revoked_at=now_utc()))
    await db.commit()
    return {"code": 0}


@router.post("/sessions/revoke-all")
async def revoke_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await revoke_user_sessions(db, user.id)
    await db.commit()
    return {"code": 0}


@router.post("/pairing")
async def pairing(user: User = Depends(get_current_user), credentials=Depends(bearer_scheme),
                  db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(credentials.credentials) or {}
    session = await db.get(UserSession, uuid.UUID(payload["sid"])) if payload.get("sid") else None
    if not session or not session.identity_id or session.created_at < now_utc() - timedelta(minutes=5):
        raise HTTPException(403, "请重新登录后生成配对码")
    await check_rate_limit(f"rl:pairing:{user.id}", 5, 600)
    code = secrets.token_hex(6).upper()
    db.add(PairingCode(user_id=user.id, code_hash=token_hash(code),
                       expires_at=now_utc() + timedelta(minutes=10)))
    await db.commit()
    return {"code": 0, "data": {"code": code, "expires_in": 600}}


@router.post("/pairing/claim")
async def claim_pair(body: PairClaim, request: Request, response: Response,
                     user: User = Depends(get_current_user), credentials=Depends(bearer_scheme),
                     db: AsyncSession = Depends(get_db)):
    await check_rate_limit(f"rl:pair_claim:{user.id}", 5, 600)
    payload = decode_access_token(credentials.credentials) or {}
    session = await db.get(UserSession, uuid.UUID(payload["sid"])) if payload.get("sid") else None
    if not session or not session.identity_id or session.created_at < now_utc() - timedelta(minutes=5):
        raise HTTPException(403, "请重新登录后绑定")
    pair = (await db.execute(select(PairingCode).where(
        PairingCode.code_hash == token_hash(body.code.strip().upper())).with_for_update())).scalar_one_or_none()
    if not pair or pair.used_at or pair.expires_at <= now_utc():
        raise HTTPException(400, "配对码无效或已过期")
    target = await db.get(User, pair.user_id, with_for_update=True)
    if not target or target.status != 1 or target.id == user.id:
        raise HTTPException(400, "配对账号不可用")
    if user.is_verified or user.role != "guest" or await db.scalar(select(func.count()).select_from(Post).where(Post.user_id == user.id)):
        raise HTTPException(409, "此账号已有认证或内容，请使用人工申诉")
    await db.get(User, user.id, with_for_update=True)
    from app.models.interaction import Comment
    from app.models.party import Party
    from app.models.student_verification import StudentIdentityClaim, StudentVerification
    for model in (Comment, Party, StudentIdentityClaim, StudentVerification):
        if await db.scalar(select(model.id).where(model.user_id == user.id).limit(1)):
            raise HTTPException(409, "此账号已有活动或认证申请，请使用人工申诉")
    identity_count = await db.scalar(select(func.count()).select_from(LoginIdentity).where(LoginIdentity.user_id == user.id))
    if identity_count != 1:
        raise HTTPException(409, "此账号已有多个登录方式，请使用人工申诉")
    identity = await db.get(LoginIdentity, session.identity_id, with_for_update=True)
    if not identity or identity.user_id != user.id:
        raise HTTPException(409, "登录身份已变化，请重新登录")
    existing = await db.scalar(select(LoginIdentity.id).where(LoginIdentity.user_id == target.id,
                                                               LoginIdentity.provider == identity.provider))
    if existing:
        raise HTTPException(409, "目标账号已有此类登录方式，请通过原登录方式进入")
    identity.user_id = target.id
    if identity.provider == "password":
        target.web_password_hash = identity.password_hash
    user.status = -2
    user.web_password_hash = None
    pair.used_at = now_utc()
    await revoke_user_sessions(db, user.id)
    await db.flush()
    return _respond({"code": 0, "data": await issue_session(db, target, identity, _client(request))},
                    request, response)


@router.post("/password")
async def set_login_password(body: SetPasswordRequest, request: Request, user: User = Depends(get_current_user),
                             credentials=Depends(bearer_scheme), db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(credentials.credentials) or {}
    session = await db.get(UserSession, uuid.UUID(payload["sid"])) if payload.get("sid") else None
    if not session or session.created_at < now_utc() - timedelta(minutes=5):
        raise HTTPException(403, "请重新登录后设置登录方式")
    existing = await db.scalar(select(LoginIdentity.id).where(LoginIdentity.user_id == user.id,
                                                             LoginIdentity.provider == "password"))
    if existing:
        raise HTTPException(409, "已设置密码，请使用修改密码")
    hashed = hash_password(body.password)
    db.add(LoginIdentity(user_id=user.id, provider="password", subject=body.username, password_hash=hashed))
    user.web_password_hash = hashed
    try:
        await revoke_user_sessions(db, user.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "该登录名不可用") from None
    return {"code": 0, "message": "登录方式已设置，请重新登录"}

class RecoveryRequest(BaseModel):
    username: str = Field(min_length=2, max_length=20)
    recovery_code: str = Field(min_length=20, max_length=100)
    new_password: str = Field(min_length=10, max_length=64)


@router.post("/recovery-codes")
async def create_recovery_codes(user: User = Depends(get_current_user),
                                credentials=Depends(bearer_scheme), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import delete
    from app.models.session import RecoveryCode
    await check_rate_limit(f"rl:recovery_codes:{user.id}", 3, 3600)
    payload = decode_access_token(credentials.credentials) or {}
    session = await db.get(UserSession, uuid.UUID(payload["sid"])) if payload.get("sid") else None
    if not session or session.created_at < now_utc() - timedelta(minutes=5):
        raise HTTPException(403, "请重新登录后生成找回码")
    await db.get(User, user.id, with_for_update=True)
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = [secrets.token_hex(16).upper() for _ in range(10)]
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=token_hash(code)))
    await db.commit()
    return {"code": 0, "data": {"codes": codes, "message": "仅显示一次，请离线妥善保存；重新生成会作废旧码"}}


@router.post("/recover")
async def recover_password(body: RecoveryRequest, request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.session import RecoveryCode
    await _ip_rate(request, "account_recover", 5)
    await check_rate_limit("rl:recover:name:" + token_hash(body.username), 5, 3600)
    identity = (await db.execute(select(LoginIdentity).where(
        LoginIdentity.provider == "password", LoginIdentity.subject == body.username
    ).with_for_update())).scalar_one_or_none()
    user = await db.get(User, identity.user_id, with_for_update=True) if identity else None
    code = (await db.execute(select(RecoveryCode).where(
        RecoveryCode.code_hash == token_hash(body.recovery_code.strip().upper())
    ).with_for_update())).scalar_one_or_none()
    if not user or user.status != 1 or not code or code.used_at or code.user_id != user.id:
        raise HTTPException(401, "账号或找回凭证无效")
    code.used_at = now_utc()
    hashed = hash_password(body.new_password)
    identity.password_hash = user.web_password_hash = hashed
    await revoke_user_sessions(db, user.id)
    await db.commit()
    return {"code": 0, "message": "密码已重置，所有设备已退出，请重新登录"}
