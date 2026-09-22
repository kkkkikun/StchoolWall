"""消息通知路由。挂在 /api/v1。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.services import notification as svc

router = APIRouter()


@router.get("/notifications")
async def list_notifications(
    type: str | None = Query(None),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    items, next_cursor, has_more = await svc.list_notifications(db, user, type, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/notifications/unread-summary")
async def unread_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.unread_summary(db, user)
    return {"code": 0, "data": data}


@router.get("/notifications/{notif_id}")
async def get_notification_detail(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.get_notification(db, user, notif_id)
    if not data:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"code": 0, "data": data}


@router.post("/notifications/read-all")
async def read_all(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    n = await svc.mark_all_read(db, user)
    return {"code": 0, "message": f"已标记 {n} 条"}


@router.post("/notifications/{notif_id}/read")
async def read_one(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    ok = await svc.mark_read(db, user, notif_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"code": 0, "message": "已读"}
