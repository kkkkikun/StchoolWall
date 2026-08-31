from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.models.post import Post
from app.schemas.admin import ReportHandle
from app.services.admin import (
    handle_report,
    list_reports,
    list_users,
    update_user_status,
)
from app.services.post import set_post_pinned
from app.services.admin import (
    admin_batch_post_status,
    admin_stats,
    admin_update_post,
    admin_update_post_status,
    admin_user_detail,
    list_posts_admin,
    update_user_role,
)
from app.services import admin_log
from app.services.admin_log import list_admin_logs, log_admin_action


class PinRequest(BaseModel):
    pinned: bool


class PostUpdateRequest(BaseModel):
    content: str | None = Field(None, min_length=1, max_length=2000)
    category: str | None = Field(None, max_length=20)
    images: list[str] | None = Field(None, max_length=6)
    price: float | None = Field(None, ge=0)


class PostBatchStatusRequest(BaseModel):
    post_ids: list[int] = Field(..., min_length=1, max_length=100)
    status: int


class UserRoleUpdateRequest(BaseModel):
    role: Literal["guest", "student", "admin"]


router = APIRouter()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/reports")
async def get_reports(
    status: str | None = Query(None),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """获取举报列表（仅 admin）"""
    items, next_cursor, has_more = await list_reports(db, status, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.put("/reports/{report_id}")
async def resolve_report(
    report_id: int,
    body: ReportHandle,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """处理举报（仅 admin）：dismiss / ban_post / ban_user"""
    result = await handle_report(db, report_id, body.action, admin_id=actor.id)
    if not result:
        raise HTTPException(status_code=404, detail="举报不存在")
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await log_admin_action(db, actor, admin_log.REPORT_HANDLE,
                           target_type="report", target_id=report_id,
                           detail={"action": body.action, "post_id": result.get("post_id")},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "处理成功", "data": result}


@router.get("/users")
async def get_users(
    cursor: str | None = Query(None),
    q: str | None = Query(None, max_length=50),
    role: str | None = Query(None, max_length=20),
    is_verified: bool | None = Query(None),
    status: int | None = Query(None, ge=0, le=1),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    page: int | None = Query(None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """用户列表（仅 admin）：q 搜索（昵称/学号/真名）、角色/认证/冻结/时间筛选。"""
    items, next_cursor, has_more, total = await list_users(
        db, cursor, q=q, role=role, is_verified=is_verified, status=status,
        time_start=time_start, time_end=time_end, page=page, page_size=page_size,
    )
    data: dict = {"items": items, "next_cursor": next_cursor, "has_more": has_more}
    if total is not None:
        data.update({"total": total, "page": page, "page_size": page_size})
    return {"code": 0, "data": data}


@router.put("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    body: UserRoleUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """修改用户角色（仅 admin）；不能改自己（防锁死）。"""
    result = await update_user_role(db, user_id, body.role, actor.id)
    if result is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if result == "self_demote":
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    await log_admin_action(db, actor, admin_log.USER_ROLE, target_type="user", target_id=user_id,
                           detail={"new_role": body.role},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "角色已更新", "data": {"role": result.role}}


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """用户详情（仅 admin）：计数聚合 + 最近帖子。"""
    data = await admin_user_detail(db, user_id)
    if not data:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 0, "data": data}


@router.put("/users/{user_id}/status")
async def change_user_status(
    user_id: str,
    request: Request,
    status: int = Query(..., ge=0, le=1),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """冻结/解冻用户（仅 admin）：status=0 冻结，status=1 解冻"""
    target = await update_user_status(db, user_id, status)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    action = admin_log.USER_FREEZE if status == 0 else admin_log.USER_UNFREEZE
    await log_admin_action(db, actor, action, target_type="user", target_id=user_id,
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "success", "data": {"status": target.status}}


@router.get("/posts")
async def get_admin_posts(
    status: int | None = Query(None),
    q: str | None = Query(None, max_length=100),
    cursor: int | None = Query(None),
    post_type: str | None = Query(None, max_length=20),
    category: str | None = Query(None, max_length=20),
    author_id: str | None = Query(None, max_length=36),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    page: int | None = Query(None, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """帖子管理列表（仅 admin）：多条件筛选 + cursor/page 双分页。"""
    items, next_cursor, has_more, total = await list_posts_admin(
        db, status, q, cursor,
        post_type=post_type, category=category, author_id=author_id,
        time_start=time_start, time_end=time_end,
        page=page, page_size=page_size,
    )
    data: dict = {"items": items, "next_cursor": next_cursor, "has_more": has_more}
    if total is not None:
        data.update({"total": total, "page": page, "page_size": page_size})
    return {"code": 0, "data": data}


@router.put("/posts/{post_id}")
async def edit_post(
    post_id: int,
    body: PostUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """编辑帖子内容（仅 admin）：content/category/images/price 局部更新。"""
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="没有可更新的字段")
    post = await admin_update_post(db, post_id, data)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    await log_admin_action(db, actor, admin_log.POST_EDIT, target_type="post", target_id=post_id,
                           detail={"fields": sorted(data.keys())},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "已更新", "data": {
        "id": post.id, "content": post.content, "category": post.category,
        "images": post.images, "price": float(post.price) if post.price else None,
    }}


@router.post("/posts/batch-status")
async def batch_post_status(
    body: PostBatchStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """批量状态流转（仅 admin）：逐条走状态机，返回成功/失败明细。"""
    result = await admin_batch_post_status(db, body.post_ids, body.status)
    await log_admin_action(db, actor, admin_log.POST_BATCH, target_type="post",
                           detail={"count": len(result["succeeded"]), "status": body.status},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": f"成功 {len(result['succeeded'])} 条", "data": result}


@router.put("/posts/{post_id}/status")
async def change_post_status(
    post_id: int,
    request: Request,
    status: int = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """帖子状态流转（仅 admin）：0→1 过审 / 0→-1 拒审 / 1→-1 封禁 / -1→1 恢复。"""
    result = await admin_update_post_status(db, post_id, status)
    if result is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    if result == "invalid":
        raise HTTPException(status_code=400, detail="非法的状态流转")
    await log_admin_action(db, actor, admin_log.POST_STATUS, target_type="post", target_id=post_id,
                           detail={"new_status": status},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "操作成功", "data": {"status": result.status}}


@router.get("/stats")
async def get_admin_stats(
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """管理看板（仅 admin）。"""
    data = await admin_stats(db)
    return {"code": 0, "data": data}


@router.put("/posts/{post_id}/pin")
async def pin_post(
    post_id: int,
    body: PinRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """置顶/取消置顶帖子（仅 admin），仅首页推荐位第一页生效"""
    post = await set_post_pinned(db, post_id, body.pinned)
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在或不可置顶")
    await log_admin_action(db, actor, admin_log.POST_PIN, target_type="post", target_id=post_id,
                           detail={"pinned": body.pinned},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "置顶成功" if body.pinned else "已取消置顶", "data": {"is_pinned": post.is_pinned}}


@router.get("/logs")
async def get_admin_logs(
    action: str | None = Query(None, max_length=50),
    admin_id: str | None = Query(None, max_length=36),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """审计日志查询（仅 admin）：动作/管理员/时间范围筛选。"""
    items, next_cursor, has_more = await list_admin_logs(
        db, action=action, admin_id=admin_id,
        time_start=time_start, time_end=time_end, cursor=cursor,
    )
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}
