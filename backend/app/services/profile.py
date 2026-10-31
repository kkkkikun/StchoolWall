"""个人主页业务逻辑：公开资料、关注/粉丝列表与计数。"""
import uuid

from sqlalchemy import func, select, update
from app.models.session import LoginIdentity
from app.services.sessions import revoke_user_sessions
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import UserFollow
from app.models.post import Post
from app.models.user import User
from app.services.follow import is_following
from app.services.blocks import blocked_between, visible_author

SCHOOL_NAME = "鄂尔多斯应用技术学院"


async def get_profile(db: AsyncSession, user_id: uuid.UUID, viewer: User | None) -> dict | None:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u or (viewer and await blocked_between(db, viewer.id, user_id)):
        return None
    posts_count = await db.scalar(
        select(func.count()).select_from(Post).where(Post.user_id == user_id, Post.status != -2)
    ) or 0
    following_count = await db.scalar(
        select(func.count()).select_from(UserFollow).where(UserFollow.follower_id == user_id, visible_author(UserFollow.followee_id, viewer))
    ) or 0
    followers_count = await db.scalar(
        select(func.count()).select_from(UserFollow).where(UserFollow.followee_id == user_id, visible_author(UserFollow.follower_id, viewer))
    ) or 0
    is_self = viewer is not None and str(viewer.id) == str(user_id)
    following = await is_following(db, viewer.id, user_id) if (viewer and not is_self) else False
    return {
        "id": str(u.id),
        "nickname": u.nickname,
        "avatar_url": u.avatar_url,
        "banner_url": u.banner_url,
        "bio": u.bio,
        "is_verified": u.is_verified,
        "school": SCHOOL_NAME if u.is_verified else None,
        "posts_count": posts_count,
        "following_count": following_count,
        "followers_count": followers_count,
        "is_following": following,
        "is_self": is_self,
    }


async def list_following(db: AsyncSession, user_id: uuid.UUID, viewer: User | None) -> list[dict]:
    """user_id 关注了哪些人。"""
    if viewer and await blocked_between(db, viewer.id, user_id):
        return []
    rows = (await db.execute(
        select(User).join(UserFollow, UserFollow.followee_id == User.id)
        .where(UserFollow.follower_id == user_id, visible_author(User.id, viewer))
        .order_by(UserFollow.created_at.desc())
    )).scalars().all()
    return await _decorate(db, rows, viewer)


async def list_followers(db: AsyncSession, user_id: uuid.UUID, viewer: User | None) -> list[dict]:
    """谁关注了 user_id。"""
    if viewer and await blocked_between(db, viewer.id, user_id):
        return []
    rows = (await db.execute(
        select(User).join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.followee_id == user_id, visible_author(User.id, viewer))
        .order_by(UserFollow.created_at.desc())
    )).scalars().all()
    return await _decorate(db, rows, viewer)


async def _decorate(db: AsyncSession, users: list[User], viewer: User | None) -> list[dict]:
    follows: set[str] = set()
    if viewer and users:
        ids = [u.id for u in users]
        res = (await db.execute(
            select(UserFollow.followee_id).where(
                UserFollow.follower_id == viewer.id, UserFollow.followee_id.in_(ids)
            )
        )).scalars()
        follows = {str(x) for x in res}
    return [
        {
            "id": str(u.id),
            "nickname": u.nickname,
            "avatar_url": u.avatar_url,
            "is_verified": u.is_verified,
            "is_following": str(u.id) in follows,
        }
        for u in users
    ]


async def change_password(db: AsyncSession, user: User, old_password: str, new_password: str) -> None:
    """网页账号修改密码。微信登录用户没有 web_password_hash。"""
    from app.utils.password import hash_password, verify_password

    if not user.web_password_hash:
        raise ValueError("当前账号未设置网页密码，无需修改")
    if not verify_password(old_password, user.web_password_hash):
        raise ValueError("原密码错误")
    user.web_password_hash = hash_password(new_password)
    await db.execute(update(LoginIdentity).where(LoginIdentity.user_id == user.id, LoginIdentity.provider == "password").values(password_hash=user.web_password_hash))
    await revoke_user_sessions(db, user.id)
    await db.commit()


async def delete_account(db: AsyncSession, user: User, password: str | None = None) -> None:
    """注销账号：软删除（status=-2）+ 清理个人隐私字段，保留 openid 防重复注册。

    帖子/评论等历史内容保留，展示名统一为「已注销用户」。
    """
    from app.utils.password import verify_password

    if user.web_password_hash:
        if not password or not verify_password(password, user.web_password_hash):
            raise ValueError("密码错误，无法注销")

    await revoke_user_sessions(db, user.id)
    user.is_verified = False
    user.verified_until = None
    from sqlalchemy import delete
    from app.models.session import UserSession, RecoveryCode
    from app.models.student_verification import StudentVerification, StudentIdentityClaim
    from app.models.media import MediaAsset
    from app.services.sessions import now_utc
    from app.utils.storage import delete_private_media
    now = now_utc()
    await db.execute(update(StudentVerification).where(StudentVerification.user_id == user.id)
        .values(status="revoked", evidence_delete_after=now, student_fingerprint=None, review_reason=None))
    await db.execute(delete(StudentIdentityClaim).where(StudentIdentityClaim.user_id == user.id))
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    await db.execute(update(UserSession).where(UserSession.user_id == user.id).values(identity_id=None))
    await db.execute(delete(LoginIdentity).where(LoginIdentity.user_id == user.id))
    assets = (await db.scalars(select(MediaAsset).where(MediaAsset.owner_id == user.id,
        MediaAsset.purpose.in_(["avatars", "banners"])))).all()
    for asset in assets:
        await delete_private_media(asset.storage_key)
        asset.status, asset.public_path = "deleted", None
    user.openid = "deleted:" + str(user.id)
    user.status = -2
    user.nickname = "已注销用户"
    user.real_name = None
    user.student_id = None
    user.wechat_id = None
    user.web_password_hash = None
    user.avatar_url = None
    user.banner_url = None
    user.bio = None
    await db.commit()
