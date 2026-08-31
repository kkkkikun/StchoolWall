"""管理后台（console）账号认证：登录 / 改密 / 签发专用 token。"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.config import settings
from app.models.admin_user import AdminUser
from app.utils.password import hash_password, verify_password
from app.utils.security import create_access_token

CONSOLE_SCOPE = "admin_console"


def issue_console_token(admin: AdminUser) -> str:
    """签发 console 专用 JWT：sub=admin_user_id + scope + pwd_version，短时效。"""
    return create_access_token(
        {
            "sub": str(admin.id),
            "scope": CONSOLE_SCOPE,
            "pwd_version": admin.pwd_version,
        },
        expires_delta=timedelta(hours=settings.ADMIN_TOKEN_EXPIRE_HOURS),
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
