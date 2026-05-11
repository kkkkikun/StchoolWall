from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.tag import TagCreate
from app.services.tag import create_tag, delete_tag, list_tags

router = APIRouter()


@router.get("")
async def get_tags(db: AsyncSession = Depends(get_db)):
    """获取所有标签（公开）"""
    tags = await list_tags(db)
    return {"code": 0, "data": tags}


@router.post("")
async def new_tag(
    body: TagCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """创建标签（仅 admin）"""
    tag = await create_tag(db, body.name)
    if not tag:
        raise HTTPException(status_code=409, detail="标签名已存在")
    return {"code": 0, "data": {"id": tag.id, "name": tag.name}}


@router.delete("/{tag_id}")
async def remove_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """删除标签（仅 admin，级联清理 post_tags）"""
    ok = await delete_tag(db, tag_id)
    if not ok:
        raise HTTPException(status_code=404, detail="标签不存在")
    return {"code": 0, "message": "删除成功"}
