from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_optional_user, require_role
from app.models.interaction import Favorite, Like
from app.models.user import User
from app.schemas.post import PostBrief, PostCreate, PostListResponse, ReportRequest
from app.services.moderation import check_post_moderation
from app.utils.rate_limit import RATE_POST_CREATE, RATE_REPORT, check_rate_limit
from app.services.post import (
    create_post,
    featured_posts,
    following_feed,
    get_post_detail,
    hot_posts,
    list_posts,
    my_posts,
    report_post,
    search_posts,
    update_post_status,
)

router = APIRouter()


async def _viewer_flags(db: AsyncSession, user: User, ids: list[int]) -> tuple[set, set]:
    """批量取当前用户对一组帖子的点赞/收藏视角。"""
    liked = set((await db.execute(
        select(Like.post_id).where(Like.user_id == user.id, Like.post_id.in_(ids))
    )).scalars())
    favs = set((await db.execute(
        select(Favorite.post_id).where(Favorite.user_id == user.id, Favorite.post_id.in_(ids))
    )).scalars())
    return liked, favs


@router.get("")
async def get_posts(
    cursor: int | None = Query(None),
    post_type: str | None = Query(None),
    category: str | None = Query(None),
    tag_id: int | None = Query(None, ge=1),
    tag: str | None = Query(None, max_length=30),
    order: str | None = Query(None, pattern="^(time)$"),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """获取帖子列表（公开，游标分页，广告置顶，带互动计数与当前用户视角）"""
    items, next_cursor, has_more = await list_posts(
        db, cursor, post_type, viewer=user, category=category, order=order, tag_id=tag_id, tag_text=tag,
    )
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

    # 按用户限流：防灌水（审核频率风控之外的第一道闸）
    await check_rate_limit(f"rl:u:{user.id}:posts", *RATE_POST_CREATE)

    post = await create_post(
        db, user, body.post_type, body.content,
        body.images, body.price, body.tag_ids, body.category,
    )

    # Student 发帖需后台审核，admin 直接通过
    # 测试环境不执行后台任务（通过环境变量控制）
    if post.status == 0 and settings.ENVIRONMENT != "test":
        bg_tasks.add_task(check_post_moderation, post.id)

    return {
        "code": 0,
        "message": "发布成功" if post.status == 1 else "发布成功，图片审核中",
        "data": {"post_id": post.id, "status": post.status},
    }


@router.get("/my")
async def get_my_posts(
    status: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    """我的帖子（含待审/封禁等全部状态，软删除除外）"""
    items = await my_posts(db, user, status)
    return {"code": 0, "data": {"items": items}}


@router.get("/following")
async def following_feed_route(
    cursor: int | None = Query(None),
    tag: str | None = Query(None, max_length=30),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    """关注流：已关注用户的帖子"""
    items, next_cursor, has_more = await following_feed(db, user, cursor, tag_text=tag)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/hot")
async def hot_posts_route(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """十大热帖（公开）"""
    items = await hot_posts(db, limit)
    return {"code": 0, "data": {"items": items}}


@router.get("/featured")
async def featured_posts_route(
    cursor: int | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    tag: str | None = Query(None, max_length=30),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """精华流：经验贴等长尾内容，历史热度排序（公开可看，登录后带点赞视角）"""
    items, next_cursor, has_more = await featured_posts(db, cursor, limit, tag_text=tag)
    if user and items:
        liked_ids, fav_ids = await _viewer_flags(db, user, [it["id"] for it in items])
        for it in items:
            it["is_liked"] = it["id"] in liked_ids
            it["is_favorited"] = it["id"] in fav_ids
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


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
    """举报帖子（不影响帖子状态，仅记录；按用户限流防举报轰炸）"""
    await check_rate_limit(f"rl:u:{user.id}:reports", *RATE_REPORT)
    report = await report_post(db, post_id, user, body.reason, body.description)
    if not report:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "message": "举报成功，管理员将尽快核实"}
