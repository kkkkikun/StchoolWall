from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.admin import ReportHandle
from app.services.admin import (
    handle_report,
    list_reports,
    list_users,
    update_user_status,
)

router = APIRouter()


@router.get("/reports")
async def get_reports(
    status: str | None = Query(None),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """获取举报列表（仅 admin）"""
    items, next_cursor, has_more = await list_reports(db, status, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.put("/reports/{report_id}")
async def resolve_report(
    report_id: int,
    body: ReportHandle,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """处理举报（仅 admin）：dismiss / ban_post / ban_user"""
    result = await handle_report(db, report_id, body.action)
    if not result:
        raise HTTPException(status_code=404, detail="举报不存在")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"code": 0, "message": "处理成功", "data": result}


@router.get("/users")
async def get_users(
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """获取用户列表（仅 admin）"""
    items, next_cursor, has_more = await list_users(db, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.put("/users/{user_id}/status")
async def change_user_status(
    user_id: str,
    status: int = Query(..., ge=0, le=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """冻结/解冻用户（仅 admin）：status=0 冻结，status=1 解冻"""
    target = await update_user_status(db, user_id, status)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 0, "message": "success", "data": {"status": target.status}}
