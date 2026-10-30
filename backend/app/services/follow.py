"""关注关系业务逻辑：关注 / 取关 / 是否关注 / 关注的 userId 集合。"""
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from app.services.blocks import require_interaction
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.follow import UserFollow
from app.models.user import User


async def follow(db: AsyncSession, follower: User, followee_id: uuid.UUID) -> dict:
    if str(follower.id) == str(followee_id):
        return {"followed": False, "reason": "不能关注自己"}
    await require_interaction(db, follower.id, followee_id)
    target = await db.get(User, followee_id)
    if not target or target.status != 1:
        raise HTTPException(404, "用户不存在")
    existing = (await db.execute(
        select(UserFollow).where(
            UserFollow.follower_id == follower.id, UserFollow.followee_id == followee_id
        )
    )).scalar_one_or_none()
    if not existing:
        await db.execute(insert(UserFollow).values(follower_id=follower.id, followee_id=followee_id)
            .on_conflict_do_nothing(index_elements=[UserFollow.follower_id, UserFollow.followee_id]))
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
