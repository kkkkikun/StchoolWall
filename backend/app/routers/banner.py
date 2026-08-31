"""Banner 路由：公开轮播列表 + admin CRUD。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.schemas.banner import BannerCreate, BannerUpdate
from app.services import admin_log
from app.services.admin_log import log_admin_action
from app.services.banner import (
    _banner_to_admin_dict,
    create_banner,
    delete_banner,
    get_banner,
    list_active_banners,
    list_banners_admin,
    update_banner,
)

router = APIRouter()
admin_router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _jsonable(data: dict) -> dict:
    """detail 落 JSONB 前把 datetime 等转为字符串。"""
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in data.items()}


@router.get("/banners")
async def public_banners(db: AsyncSession = Depends(get_db)):
    """首页轮播广告位（公开，仅投放中的）。"""
    items = await list_active_banners(db)
    return {"code": 0, "data": {"items": items}}


@admin_router.get("/banners")
async def admin_list_banners(
    status: int | None = Query(None, ge=0, le=1),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """Banner 管理列表（全量，含下架）。"""
    items, next_cursor, has_more = await list_banners_admin(db, status, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@admin_router.post("/banners")
async def admin_create_banner(
    body: BannerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """创建 Banner（仅 admin）。"""
    banner = await create_banner(db, body.model_dump())
    await log_admin_action(db, actor, admin_log.BANNER_CREATE, target_type="banner",
                           target_id=banner.id, detail={"title": banner.title},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "创建成功", "data": _banner_to_admin_dict(banner)}


@admin_router.put("/banners/{banner_id}")
async def admin_update_banner(
    banner_id: int,
    body: BannerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """更新 Banner（仅 admin），未提供的字段保持原值。"""
    banner = await get_banner(db, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    data = body.model_dump(exclude_unset=True)
    banner = await update_banner(db, banner, data)
    await log_admin_action(db, actor, admin_log.BANNER_UPDATE, target_type="banner",
                           target_id=banner_id, detail=_jsonable(data),
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "更新成功", "data": _banner_to_admin_dict(banner)}


@admin_router.delete("/banners/{banner_id}")
async def admin_delete_banner(
    banner_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """删除 Banner（仅 admin）。"""
    banner = await get_banner(db, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    title = banner.title
    await delete_banner(db, banner)
    await log_admin_action(db, actor, admin_log.BANNER_DELETE, target_type="banner",
                           target_id=banner_id, detail={"title": title},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "删除成功"}
