from datetime import datetime
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
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
from app.services.admin_comment import admin_delete_comment, list_comments_admin
from app.services.admin_export import iter_posts_csv, iter_users_csv
from app.services.admin_log import list_admin_logs, log_admin_action
from app.services.admin_party import admin_update_party_status, list_parties_admin
from app.services.admin_stats import MAX_DAYS as TRENDS_MAX_DAYS, admin_stats_trends
from app.services.announcement import create_announcement, list_announcements


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


class AnnouncementRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=2000)
    audience: Literal["all", "verified"] = "all"


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


# ---- 评论管理 ----


@router.get("/comments")
async def get_admin_comments(
    q: str | None = Query(None, max_length=100),
    post_id: int | None = Query(None),
    status: int | None = Query(None),
    time_start: datetime | None = Query(None),
    time_end: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """评论列表（仅 admin）：搜索/帖子/状态/时间筛选。"""
    items, total = await list_comments_admin(
        db, q=q, post_id=post_id, status=status,
        time_start=time_start, time_end=time_end, page=page, page_size=page_size,
    )
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """软删评论（仅 admin）。"""
    result = await admin_delete_comment(db, comment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    await log_admin_action(db, actor, admin_log.COMMENT_DELETE, target_type="comment",
                           target_id=comment_id, ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "已删除"}


# ---- 组局管理 ----


@router.get("/parties")
async def get_admin_parties(
    q: str | None = Query(None, max_length=100),
    status: int | None = Query(None),
    type: str | None = Query(None, max_length=10),
    category: str | None = Query(None, max_length=20),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """组局列表（仅 admin）。"""
    items, total = await list_parties_admin(
        db, q=q, status=status, type=type, category=category, page=page, page_size=page_size,
    )
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.put("/parties/{party_id}/status")
async def change_party_status(
    party_id: int,
    request: Request,
    status: int = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """组局关闭/恢复（仅 admin）：1/2→-1 关闭，-1→1 恢复。"""
    result = await admin_update_party_status(db, party_id, status)
    if result is None:
        raise HTTPException(status_code=404, detail="组局不存在")
    if result == "invalid":
        raise HTTPException(status_code=400, detail="非法的状态流转")
    await log_admin_action(db, actor, admin_log.PARTY_STATUS, target_type="party",
                           target_id=party_id, detail={"new_status": status},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "操作成功", "data": {"status": result.status}}


# ---- 公告群发 ----


@router.post("/announcements")
async def send_announcement(
    body: AnnouncementRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """群发公告（仅 admin）：all=全部 / verified=仅认证用户。"""
    try:
        result = await create_announcement(
            db, actor, title=body.title, content=body.content, audience=body.audience,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_admin_action(db, actor, admin_log.ANNOUNCEMENT_SEND,
                           target_type="announcement", target_id=result["batch_id"],
                           detail={"title": body.title, "audience": body.audience,
                                   "recipients": result["recipients"]},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": f"已发送给 {result['recipients']} 位用户", "data": result}


@router.get("/announcements")
async def get_announcements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """公告历史（仅 admin）：按批次聚合。"""
    items, total = await list_announcements(db, page=page, page_size=page_size)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


# ---- 趋势 / 导出 ----


@router.get("/stats/trends")
async def get_admin_trends(
    days: int = Query(14, ge=1, le=TRENDS_MAX_DAYS),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """看板趋势（仅 admin）：按日聚合 posts/comments/likes/new_users/active_users。"""
    data = await admin_stats_trends(db, days)
    return {"code": 0, "data": data}


@router.get("/export/posts")
async def export_posts(
    status: int | None = Query(None),
    q: str | None = Query(None, max_length=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """帖子 CSV 导出（流式，UTF-8 BOM）。"""
    from fastapi.responses import StreamingResponse

    async def gen():
        async for chunk in iter_posts_csv(db, status=status, q=q):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=posts.csv"},
    )


@router.get("/export/users")
async def export_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """用户 CSV 导出（含敏感字段，强制审计）。"""
    from fastapi.responses import StreamingResponse

    async def gen():
        async for chunk in iter_users_csv(db, actor, ip=_client_ip(request)):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


# ---- 图片上传（Banner 等） ----


@router.post("/upload/image")
async def admin_upload_image(
    request: Request,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """管理端图片上传：存 banners/{年}/{uuid}.ext，返回可访问的 public_url。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    from app.utils.storage import MAX_FILE_SIZE, get_storage_backend, validate_file

    err = validate_file(file.filename, file.content_type or "")
    if err:
        raise HTTPException(status_code=400, detail=err)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    # 强制 banners/ 前缀 + 随机文件名（不接受客户端 path，防穿越）
    from pathlib import Path as _Path
    ext = _Path(file.filename).suffix.lower()
    path = f"banners/{datetime.now().year}/{uuid.uuid4().hex}{ext}"

    backend = get_storage_backend()
    if not hasattr(backend, "save_upload"):
        raise HTTPException(status_code=400, detail="当前存储模式不支持直接上传")

    await file.seek(0)
    try:
        public_url = await backend.save_upload(file, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_admin_action(db, actor, admin_log.IMAGE_UPLOAD, target_type="banner",
                           detail={"path": path, "filename": file.filename},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "上传成功", "data": {"public_url": public_url, "path": path}}
