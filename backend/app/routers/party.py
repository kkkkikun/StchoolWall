"""组局路由。挂在 /api/v1。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_optional_user, require_role
from app.models.user import User
from app.services import party as svc

router = APIRouter()


class PartyCreate(BaseModel):
    type: str = Field(..., pattern=r"^(group|purchase)$")
    category: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=2000)
    total: int = Field(..., ge=1, le=999)
    location: str | None = Field(None, max_length=100)


@router.get("/parties/summary")
async def parties_summary(db: AsyncSession = Depends(get_db)):
    """累计攒局人数（公开）"""
    return {"code": 0, "data": {"total_members": await svc.total_members(db)}}


@router.get("/parties")
async def list_parties(
    category: str | None = Query(None),
    only_vacant: bool = Query(False),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    items, next_cursor, has_more = await svc.list_parties(db, category, only_vacant, cursor, viewer=user)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.post("/parties")
async def create_party(
    body: PartyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    p = await svc.create_party(
        db, user, body.type, body.category, body.title, body.content, body.total, location=body.location
    )
    return {"code": 0, "data": svc._party_dict(p, user.nickname, is_joined=False)}


@router.post("/parties/{party_id}/join")
async def join_party(
    party_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.join_party(db, user, party_id)
    if data is None:
        raise HTTPException(status_code=404, detail="组局不存在")
    return {"code": 0, "data": data}


@router.delete("/parties/{party_id}/join")
async def leave_party(
    party_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.leave_party(db, user, party_id)
    if data is None:
        raise HTTPException(status_code=404, detail="组局不存在")
    return {"code": 0, "data": data}


@router.get("/me/parties")
async def my_parties(
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    items, next_cursor, has_more = await svc.my_parties(db, user, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}
