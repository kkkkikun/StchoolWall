import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.session import LoginIdentity, UserSession, SpentRefreshToken, PairingCode
from app.models.user import User
from app.utils.security import create_access_token

def now_utc():
    return datetime.now(timezone.utc)

def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def session_payload(user: User, session: UserSession, refresh: str) -> dict:
    token = create_access_token({"sub": str(user.id), "sid": str(session.id),
        "sv": session.token_version, "role": user.role, "scope": "user"})
    return {"access_token": token, "refresh_token": refresh, "session_id": str(session.id),
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60, "role": user.role,
        "user_info": {"id": str(user.id), "nickname": user.nickname, "is_verified": user.is_verified}}

async def issue_session(db: AsyncSession, user: User, identity: LoginIdentity | None = None,
                        client_type: str = "native") -> dict:
    raw = secrets.token_urlsafe(48)
    session = UserSession(user_id=user.id, identity_id=identity.id if identity else None,
        refresh_hash=token_hash(raw), client_type=client_type,
        expires_at=now_utc() + timedelta(days=settings.REFRESH_EXPIRE_DAYS))
    db.add(session)
    await db.commit()
    return session_payload(user, session, raw)

async def revoke_user_sessions(db: AsyncSession, user_id) -> None:
    await db.execute(update(PairingCode).where(PairingCode.user_id == user_id,
        PairingCode.used_at.is_(None)).values(used_at=now_utc()))
    await db.execute(update(UserSession).where(UserSession.user_id == user_id,
        UserSession.revoked_at.is_(None)).values(revoked_at=now_utc()))

async def refresh_session(db: AsyncSession, raw: str) -> dict:
    hashed = token_hash(raw)
    session = (await db.execute(select(UserSession).where(or_(
        UserSession.refresh_hash == hashed, UserSession.previous_refresh_hash == hashed))
        .with_for_update())).scalar_one_or_none()
    if not session:
        spent = await db.get(SpentRefreshToken, hashed)
        if spent:
            family = await db.get(UserSession, spent.session_id, with_for_update=True)
            if family:
                await revoke_user_sessions(db, family.user_id)
                await db.commit()
        raise HTTPException(401, "登录已失效，请重新登录")
    if session.previous_refresh_hash == hashed:
        await revoke_user_sessions(db, session.user_id)
        await db.commit()
        raise HTTPException(401, "刷新凭证已重复使用，请重新登录")
    user = await db.get(User, session.user_id)
    if session.revoked_at or session.expires_at <= now_utc() or not user or user.status != 1:
        raise HTTPException(401, "登录已失效，请重新登录")
    raw = secrets.token_urlsafe(48)
    db.add(SpentRefreshToken(token_hash=session.refresh_hash, session_id=session.id, expires_at=session.expires_at))
    session.previous_refresh_hash = session.refresh_hash
    session.refresh_hash = token_hash(raw)
    session.token_version += 1
    session.last_seen_at = now_utc()
    await db.commit()
    return session_payload(user, session, raw)

async def validate_session(db: AsyncSession, user: User, payload: dict) -> UserSession | None:
    sid = payload.get("sid")
    if not sid and settings.ENVIRONMENT == "test":
        return None
    try:
        session_id = uuid.UUID(sid)
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(401, "会话已失效，请重新登录") from None
    session = await db.get(UserSession, session_id)
    if (not session or session.user_id != user.id or session.revoked_at or
        session.expires_at <= now_utc() or session.token_version != payload.get("sv")):
        raise HTTPException(401, "会话已失效，请重新登录")
    return session

async def cleanup_sessions(db: AsyncSession) -> None:
    from sqlalchemy import delete
    from app.models.session import PairingCode
    now = now_utc()
    await db.execute(delete(SpentRefreshToken).where(SpentRefreshToken.expires_at < now))
    await db.execute(delete(PairingCode).where(PairingCode.expires_at < now))
    await db.execute(delete(UserSession).where(
        UserSession.expires_at < now - timedelta(days=7),
        ~UserSession.id.in_(select(SpentRefreshToken.session_id)),
    ))
    await db.commit()