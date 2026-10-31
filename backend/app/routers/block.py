"""Account block management; requests are idempotent and affect both interaction directions."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.block import UserBlock
from app.models.user import User
from app.services.blocks import remove_block, set_block
from app.utils.rate_limit import check_rate_limit

router = APIRouter()


@router.post("/users/{user_id}/block")
async def block_user(user_id: uuid.UUID, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    await check_rate_limit(f"rl:u:{user.id}:blocks", 30, 3600)
    try:
        await set_block(db, user, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return {"code": 0, "data": {"blocked": True}}


@router.delete("/users/{user_id}/block")
async def unblock_user(user_id: uuid.UUID, user: User = Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    await remove_block(db, user, user_id)
    await db.commit()
    return {"code": 0, "data": {"blocked": False}}


@router.get("/user/blocks")
async def list_blocks(cursor: uuid.UUID | None = None, limit: int = Query(20, ge=1, le=100),
                      user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conditions = [UserBlock.blocker_id == user.id]
    if cursor:
        conditions.append(UserBlock.blocked_id > cursor)
    rows = list((await db.execute(select(User).join(
        UserBlock, UserBlock.blocked_id == User.id,
    ).where(*conditions).order_by(UserBlock.blocked_id).limit(limit + 1))).scalars())
    more, rows = len(rows) > limit, rows[:limit]
    return {"code": 0, "data": {"items": [{"id": str(row.id), "nickname": row.nickname} for row in rows],
            "has_more": more, "next_cursor": str(rows[-1].id) if more and rows else None}}
