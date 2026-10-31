"""Shared mutual block predicates for discovery and write authorization."""
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import UserBlock
from app.models.follow import UserFollow
from app.models.user import User


def visible_author(column, viewer: User | None):
    if viewer is None:
        return true()
    hidden = select(UserBlock.blocked_id).where(UserBlock.blocker_id == viewer.id).union(
        select(UserBlock.blocker_id).where(UserBlock.blocked_id == viewer.id))
    return column.not_in(hidden)


async def blocked_between(db: AsyncSession, first_id: uuid.UUID, second_id: uuid.UUID) -> bool:
    if first_id == second_id:
        return False
    return bool(await db.scalar(select(UserBlock.blocker_id).where(or_(
        (UserBlock.blocker_id == first_id) & (UserBlock.blocked_id == second_id),
        (UserBlock.blocker_id == second_id) & (UserBlock.blocked_id == first_id),
    )).limit(1)))


async def require_interaction(db: AsyncSession, actor_id: uuid.UUID, target_id: uuid.UUID) -> None:
    if await blocked_between(db, actor_id, target_id):
        raise HTTPException(status_code=403, detail="存在拉黑关系，无法进行此互动")


async def set_block(db: AsyncSession, actor: User, target_id: uuid.UUID) -> None:
    if actor.id == target_id:
        raise ValueError("不能拉黑自己")
    target = await db.get(User, target_id)
    if target is None or target.status != 1:
        raise ValueError("用户不存在")
    await db.execute(insert(UserBlock).values(blocker_id=actor.id, blocked_id=target_id)
                     .on_conflict_do_nothing(index_elements=[UserBlock.blocker_id, UserBlock.blocked_id]))
    await db.execute(delete(UserFollow).where(or_(
        (UserFollow.follower_id == actor.id) & (UserFollow.followee_id == target_id),
        (UserFollow.follower_id == target_id) & (UserFollow.followee_id == actor.id),
    )))


async def remove_block(db: AsyncSession, actor: User, target_id: uuid.UUID) -> None:
    await db.execute(delete(UserBlock).where(
        UserBlock.blocker_id == actor.id, UserBlock.blocked_id == target_id,
    ))
