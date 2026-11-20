"""管理后台（console）账号认证：登录 / 改密 / 签发专用 token。"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.config import settings
from app.models.admin_user import AdminUser
from app.utils.password import hash_password, verify_password
from app.utils.query import escape_like
from app.utils.security import create_access_token

CONSOLE_SCOPE = "admin_console"
MFA_SETUP_SCOPE = "admin_mfa_setup"


def issue_console_token(admin: AdminUser, mfa: bool = False) -> str:
    """签发 console 专用 JWT：sub=admin_user_id + scope + pwd_version，短时效。"""
    return create_access_token(
        {
            "sub": str(admin.id),
            "scope": CONSOLE_SCOPE,
            "mfa": mfa,
            "pwd_version": admin.pwd_version,
        },
        expires_delta=timedelta(hours=settings.ADMIN_TOKEN_EXPIRE_HOURS),
    )


def issue_mfa_setup_token(admin: AdminUser, encrypted_secret: str) -> str:
    """首次绑定令牌只能携带本次加密密钥，不能访问任何管理接口。"""
    return create_access_token(
        {
            "sub": str(admin.id),
            "scope": MFA_SETUP_SCOPE,
            "pwd_version": admin.pwd_version,
            "mfa_secret": encrypted_secret,
        },
        expires_delta=timedelta(minutes=10),
    )


async def authenticate_admin(db: AsyncSession, username: str, password: str) -> AdminUser | None:
    """校验用户名密码；成功更新 last_login_at 并返回账号，失败返回 None。"""
    result = await db.execute(select(AdminUser).where(AdminUser.username == username))
    admin = result.scalar_one_or_none()
    if admin is None:
        # 仍做一次哈希比较，避免用户名枚举的时间差
        verify_password(password, "$2b$12$invalidinvalidinvalidinvalidinvalidinvalidinvalidinvalidinv")
        return None
    if not admin.is_active or not verify_password(password, admin.password_hash):
        return None
    admin.last_login_at = func.now()
    await db.commit()
    await db.refresh(admin)
    return admin


async def change_admin_password(
    db: AsyncSession, admin: AdminUser, old_password: str, new_password: str
) -> bool:
    """改密：校验旧密码，成功则换哈希并 pwd_version+1（所有旧 token 失效）。"""
    if not verify_password(old_password, admin.password_hash):
        return False
    admin.password_hash = hash_password(new_password)
    admin.pwd_version += 1
    await db.commit()
    return True


async def get_admin_by_id(db: AsyncSession, admin_id: str) -> AdminUser | None:
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    return result.scalar_one_or_none()


async def create_or_reset_admin(
    db: AsyncSession, username: str, nickname: str, password: str, reset: bool = False
) -> tuple[AdminUser, bool]:
    """创建管理员；已存在时 reset=True 覆盖密码，否则原样返回。返回 (admin, created)。"""
    result = await db.execute(select(AdminUser).where(AdminUser.username == username))
    admin = result.scalar_one_or_none()
    if admin is not None:
        if reset:
            admin.password_hash = hash_password(password)
            admin.nickname = nickname or admin.nickname
            admin.is_active = True
            admin.pwd_version += 1
            await db.commit()
            await db.refresh(admin)
        return admin, False

    admin = AdminUser(
        username=username,
        nickname=nickname or username,
        password_hash=hash_password(password),
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin, True


async def list_admin_users(
    db: AsyncSession,
    *,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """管理后台账号列表（昵称/用户名模糊搜索 + 分页）。"""
    conditions = []
    if q:
        like = f"%{escape_like(q)}%"
        conditions.append(AdminUser.username.ilike(like) | AdminUser.nickname.ilike(like))

    total = await db.scalar(
        select(func.count()).select_from(AdminUser).where(*conditions)
    ) or 0

    stmt = (
        select(AdminUser)
        .where(*conditions)
        .order_by(AdminUser.created_at.desc(), AdminUser.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    admins = (await db.execute(stmt)).scalars().all()
    items = [{
        "id": str(a.id),
        "username": a.username,
        "nickname": a.nickname,
        "role": a.role,
        "mfa_enabled": bool(a.mfa_secret_encrypted),
        "is_active": bool(a.is_active),
        "pwd_version": a.pwd_version,
        "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    } for a in admins]
    return items, total


async def create_admin_user(
    db: AsyncSession, username: str, nickname: str, password: str, role: str = "admin"
) -> tuple[AdminUser | None, str | None]:
    """新建管理后台账号；用户名冲突返回错误信息。"""
    username = username.strip()
    if len(username) < 3:
        return None, "用户名至少 3 位"
    nickname = (nickname or "").strip() or username
    result = await db.execute(select(AdminUser).where(AdminUser.username == username))
    if result.scalar_one_or_none() is not None:
        return None, "用户名已存在"

    admin = AdminUser(
        username=username,
        nickname=nickname,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin, None


async def set_admin_active(
    db: AsyncSession,
    admin_id: str,
    is_active: bool,
    *,
    actor_id: str | None = None,
) -> tuple[AdminUser | None, str | None]:
    """启用/停用账号，不能停用自己或最后一个启用的超级管理员。"""
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        return None, "管理员不存在"

    if not is_active:
        if actor_id is not None and str(admin.id) == str(actor_id):
            return admin, "不能停用当前登录账号"
        if admin.role == "owner":
            owner_count = await db.scalar(
                select(func.count())
                .select_from(AdminUser)
                .where(
                    AdminUser.is_active.is_(True),
                    AdminUser.role == "owner",
                    AdminUser.id != admin.id,
                )
            ) or 0
            if owner_count == 0:
                return admin, "至少保留一个启用的超级管理员"
        else:
            active_count = await db.scalar(
                select(func.count())
                .select_from(AdminUser)
                .where(AdminUser.is_active.is_(True), AdminUser.id != admin.id)
            ) or 0
            if active_count == 0:
                return admin, "至少保留一个启用账号"

    admin.is_active = is_active
    await db.commit()
    await db.refresh(admin)
    return admin, None


async def reset_admin_password(
    db: AsyncSession,
    admin_id: str,
    new_password: str,
    *,
    actor_id: str | None = None,
) -> tuple[AdminUser | None, str | None]:
    """强制重置其他管理员密码；pwd_version+1 使其旧 token 全部失效。"""
    result = await db.execute(select(AdminUser).where(AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        return None, "管理员不存在"

    if actor_id is not None and str(admin.id) == str(actor_id):
        return admin, "请使用右上角「修改密码」修改自己的密码"

    admin.password_hash = hash_password(new_password)
    admin.pwd_version += 1
    await db.commit()
    await db.refresh(admin)
    return admin, None
