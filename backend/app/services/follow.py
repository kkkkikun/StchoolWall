"""关注关系业务逻辑：关注 / 取关 / 是否关注 / 关注的 userId 集合。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import UserFollow
from app.models.user import User


async def follow(db: AsyncSession, follower: User, followee_id: uuid.UUID) -> dict:
    if str(follower.id) == str(followee_id):
        return {"followed": False, "reason": "不能关注自己"}
    existing = (await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == follower.id, UserFollow.followee_id == followee_id
        )
    )).scalar_one_or_none()
    if not existing:
        db.add(UserFollow(follower_id=follower.id, followee_id=followee_id))
        await db.commit()
    return {"followed": True}


async def unfollow(db: AsyncSession, follower: User, followee_id: uuid.UUID) -> dict:
    f = (await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == follower.id, UserFollow.followee_id == followee_id
        )
    )).scalar_one_or_none()
    if f:
        await db.delete(f)
        await db.commit()
    return {"followed": False}


async def is_following(db: AsyncSession, follower_id: uuid.UUID, followee_id: uuid.UUID) -> bool:
    if str(follower_id) == str(followee_id):
        return False
    f = (await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == follower_id, UserFollow.followee_id == followee_id
        )
    )).scalar_one_or_none()
    return f is not None
