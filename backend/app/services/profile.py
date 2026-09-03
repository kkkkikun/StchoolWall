"""个人主页业务逻辑：公开资料、关注/粉丝列表与计数。"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import UserFollow
from app.models.post import Post
from app.models.user import User
from app.services.follow import is_following

SCHOOL_NAME = "鄂尔多斯应用技术学院"


async def get_profile(db: AsyncSession, user_id: uuid.UUID, viewer: User | None) -> dict | None:
    u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not u:
        return None
    posts_count = await db.scalar(
        select(func.count()).select_from(Post).where(Post.user_id == user_id, Post.status != -2)
    ) or 0
    following_count = await db.scalar(
        select(func.count()).select_from(UserFollow).where(UserFollow.follower_id == user_id)
    ) or 0
    followers_count = await db.scalar(
        select(func.count()).select_from(UserFollow).where(UserFollow.followee_id == user_id)
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
    rows = (await db.execute(
        select(User).join(UserFollow, UserFollow.followee_id == User.id)
        .where(UserFollow.follower_id == user_id)
        .order_by(UserFollow.created_at.desc())
    )).scalars().all()
    return await _decorate(db, rows, viewer)


async def list_followers(db: AsyncSession, user_id: uuid.UUID, viewer: User | None) -> list[dict]:
    """谁关注了 user_id。"""
    rows = (await db.execute(
        select(User).join(UserFollow, UserFollow.follower_id == User.id)
        .where(UserFollow.followee_id == user_id)
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
