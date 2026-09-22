"""标签路由：公开列表 + admin CRUD。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.schemas.tag import TagCreate
from app.services import admin_log
from app.services.admin_log import log_admin_action
from app.services.tag import create_tag, delete_tag, list_tags

router = APIRouter()
admin_router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("")
async def get_tags(db: AsyncSession = Depends(get_db)):
    """获取所有标签（公开）。"""
    tags = await list_tags(db)
    return {"code": 0, "data": tags}


@admin_router.get("/tags")
async def admin_list_tags(
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """标签管理列表（仅 admin，含公开列表同款数据）。"""
    tags = await list_tags(db)
    return {"code": 0, "data": {"items": tags}}


@admin_router.post("/tags")
async def admin_create_tag(
    body: TagCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """创建标签（仅 admin），并写审计日志。"""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="标签名不能为空")
    tag = await create_tag(db, name)
    if not tag:
        raise HTTPException(status_code=409, detail="标签名已存在")
    await log_admin_action(db, actor, admin_log.TAG_CREATE,
                           target_type="tag", target_id=tag.id,
                           detail={"name": tag.name}, ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "创建成功", "data": {"id": tag.id, "name": tag.name}}


@admin_router.delete("/tags/{tag_id}")
async def admin_delete_tag(
    tag_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """删除标签（仅 admin，级联清理 post_tags），并写审计日志。"""
    tag = (await list_tags(db))
    target = next((t for t in tag if t["id"] == tag_id), None)
    ok = await delete_tag(db, tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="标签不存在")
    await log_admin_action(db, actor, admin_log.TAG_DELETE,
                           target_type="tag", target_id=tag_id,
                           detail={"name": target["name"] if target else None},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "删除成功"}
