from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_optional_user, require_role
from app.models.user import User
from app.schemas.post import PostBrief, PostCreate, PostListResponse, ReportRequest
from app.services.moderation import check_post_images
from app.services.post import (
    create_post,
    get_post_detail,
    hot_posts,
    list_posts,
    report_post,
    search_posts,
    update_post_status,
)

router = APIRouter()


@router.get("")
async def get_posts(
    cursor: int | None = Query(None),
    post_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """获取帖子列表（公开，游标分页，广告置顶，带互动计数与当前用户视角）"""
    items, next_cursor, has_more = await list_posts(db, cursor, post_type, viewer=user)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.post("")
async def new_post(
    body: PostCreate,
    bg_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    """发布帖子（admin 可发广告且跳过审核）"""
    # 只有 admin 能发 advertisement
    if body.post_type == "advertisement" and user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可发布广告")

    post = await create_post(
        db, user, body.post_type, body.content,
        body.images, body.price, body.tag_ids,
    )

    # Student 发帖需后台审核，admin 直接通过
    # 测试环境不执行后台任务（通过环境变量控制）
    if post.status == 0 and settings.ENVIRONMENT != "test":
        bg_tasks.add_task(check_post_images, post.id)

    return {
        "code": 0,
        "message": "发布成功" if post.status == 1 else "发布成功，图片审核中",
        "data": {"post_id": post.id, "status": post.status},
    }


@router.get("/hot")
async def hot_posts_route(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """十大热帖（公开）"""
    items = await hot_posts(db, limit)
    return {"code": 0, "data": {"items": items}}


@router.get("/search")
async def search_posts_route(
    q: str = Query(..., min_length=1),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """帖子搜索（公开）"""
    items, next_cursor, has_more = await search_posts(db, q, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/{post_id}")
async def get_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """获取帖子详情（含隐私隔离）"""
    data = await get_post_detail(db, post_id, user)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "data": data}


@router.put("/{post_id}/status")
async def change_status(
    post_id: int,
    status: int = Query(..., ge=-2, le=2),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    """变更帖子状态（归档/删除/封禁）"""
    post = await update_post_status(db, post_id, user, status)
    if not post:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="操作不允许或帖子不存在")
    return {"code": 0, "message": "success", "data": {"status": post.status}}


@router.post("/{post_id}/report")
async def submit_report(
    post_id: int,
    body: ReportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    """举报帖子（不影响帖子状态，仅记录）"""
    report = await report_post(db, post_id, user, body.reason, body.description)
    if not report:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "message": "举报成功，管理员将尽快核实"}
