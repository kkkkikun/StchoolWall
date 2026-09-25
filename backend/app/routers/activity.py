"""活动/专题页路由：公开详情 + admin CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.schemas.activity import ActivityCreate, ActivityUpdate
from app.services import admin_log
from app.services.activity import (
    create_activity,
    delete_activity,
    get_activity,
    get_public_activity,
    list_admin_activities,
    update_activity,
)
from app.services.admin_log import log_admin_action

router = APIRouter()
admin_router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/activities/{activity_id}")
async def public_activity_detail(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
):
    """公开活动详情（仅上架）。"""
    data = await get_public_activity(db, activity_id)
    if not data:
        raise HTTPException(status_code=404, detail="活动不存在或已下架")
    return {"code": 0, "data": data}


@admin_router.get("/activities")
async def admin_list_activities(
    q: str | None = Query(None, max_length=100),
    status: int | None = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """活动管理列表（仅 admin）。"""
    items, total = await list_admin_activities(db, q=q, status=status, page=page, page_size=page_size)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@admin_router.post("/activities")
async def admin_create_activity(
    body: ActivityCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """新建活动（仅 admin）。"""
    a = await create_activity(db, body.model_dump())
    await log_admin_action(db, actor, admin_log.ACTIVITY_CREATE,
                           target_type="activity", target_id=a.id,
                           detail={"title": a.title}, ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "创建成功", "data": {"id": a.id, "title": a.title}}


@admin_router.put("/activities/{activity_id}")
async def admin_update_activity(
    activity_id: int,
    body: ActivityUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """编辑活动（仅 admin）。"""
    a = await get_activity(db, activity_id)
    if not a:
        raise HTTPException(status_code=404, detail="活动不存在")
    data = body.model_dump(exclude_unset=True)
    if data:
        a = await update_activity(db, a, data)
    await log_admin_action(db, actor, admin_log.ACTIVITY_UPDATE,
                           target_type="activity", target_id=activity_id,
                           detail={"title": a.title}, ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "已更新", "data": {"id": a.id, "title": a.title}}


@admin_router.delete("/activities/{activity_id}")
async def admin_delete_activity(
    activity_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """删除活动（仅 admin）。"""
    a = await get_activity(db, activity_id)
    if not a:
        raise HTTPException(status_code=404, detail="活动不存在")
    title = a.title
    await delete_activity(db, a)
    await log_admin_action(db, actor, admin_log.ACTIVITY_DELETE,
                           target_type="activity", target_id=activity_id,
                           detail={"title": title}, ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "删除成功"}
