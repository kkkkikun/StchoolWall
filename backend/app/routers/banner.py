"""Banner 路由：公开轮播列表 + admin CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.banner import BannerCreate, BannerUpdate
from app.services.banner import (
    create_banner,
    delete_banner,
    get_banner,
    list_active_banners,
    list_banners_admin,
    update_banner,
)

router = APIRouter()
admin_router = APIRouter()


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
    user: User = Depends(require_role("admin")),
):
    """Banner 管理列表（全量，含下架）。"""
    items, next_cursor, has_more = await list_banners_admin(db, status, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@admin_router.post("/banners")
async def admin_create_banner(
    body: BannerCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """创建 Banner（仅 admin）。"""
    banner = await create_banner(db, body.model_dump())
    from app.services.banner import _banner_to_admin_dict
    return {"code": 0, "message": "创建成功", "data": _banner_to_admin_dict(banner)}


@admin_router.put("/banners/{banner_id}")
async def admin_update_banner(
    banner_id: int,
    body: BannerUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """更新 Banner（仅 admin），未提供的字段保持原值。"""
    banner = await get_banner(db, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    data = body.model_dump(exclude_unset=True)
    banner = await update_banner(db, banner, data)
    from app.services.banner import _banner_to_admin_dict
    return {"code": 0, "message": "更新成功", "data": _banner_to_admin_dict(banner)}


@admin_router.delete("/banners/{banner_id}")
async def admin_delete_banner(
    banner_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """删除 Banner（仅 admin）。"""
    banner = await get_banner(db, banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    await delete_banner(db, banner)
    return {"code": 0, "message": "删除成功"}
