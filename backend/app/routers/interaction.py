from app.services.runtime_controls import require_publishing
"""互动路由：评论 / 点赞 / 收藏 / 足迹 / 个人统计。

挂在 /api/v1 下，与 posts 路由并存（路径不重叠）。
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_optional_user, require_role
from app.models.user import User
from app.schemas.interaction import CommentCreate
from app.services import interaction as svc
from app.services import follow as follow_svc
from app.services import profile as profile_svc
from app.services.post import user_posts
from app.utils.rate_limit import RATE_COMMENT, check_rate_limit

router = APIRouter()


# ---- 点赞 ----


@router.post("/posts/{post_id}/like")
async def like_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.like_post(db, user, post_id)
    if data is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "data": data}


@router.delete("/posts/{post_id}/like")
async def unlike_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.unlike_post(db, user, post_id)
    if data is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "data": data}


# ---- 评论 ----


@router.post("/posts/{post_id}/comments", dependencies=[Depends(require_publishing)])
async def create_comment(
    post_id: int,
    body: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    await check_rate_limit(f"rl:u:{user.id}:comments", *RATE_COMMENT)
    try:
        data = await svc.create_comment(db, user, post_id, body.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if data is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "data": data}


@router.get("/posts/{post_id}/comments")
async def list_comments(
    post_id: int,
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    # 目标帖必须是公开可见状态（封禁/待审帖的评论不可读）
    if not await svc._get_post(db, post_id, viewer=user):
        raise HTTPException(status_code=404, detail="帖子不存在")
    items, next_cursor, has_more = await svc.list_comments(db, post_id, cursor, viewer=user)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    result = await svc.delete_comment(db, user, comment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="评论不存在")
    if result is False:
        raise HTTPException(status_code=403, detail="无权删除该评论")
    return {"code": 0, "message": "已删除"}


# ---- 收藏 ----


@router.post("/posts/{post_id}/favorite")
async def favorite_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.favorite_post(db, user, post_id)
    if data is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "data": data}


@router.delete("/posts/{post_id}/favorite")
async def unfavorite_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.unfavorite_post(db, user, post_id)
    if data is None:
        raise HTTPException(status_code=404, detail="帖子不存在")
    return {"code": 0, "data": data}


# ---- 我的 ----


@router.get("/me/favorites")
async def my_favorites(
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    items, next_cursor, has_more = await svc.list_favorites(db, user, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/me/likes")
async def my_likes(
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    items, next_cursor, has_more = await svc.list_my_likes(db, user, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/me/comments")
async def my_comments(
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    items, next_cursor, has_more = await svc.list_my_comments(db, user, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/me/footprints")
async def my_footprints(
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    items, next_cursor, has_more = await svc.list_footprints(db, user, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}


@router.get("/me/stats")
async def my_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    data = await svc.get_stats(db, user)
    return {"code": 0, "data": data}


# ---- 关注 ----


@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    import uuid as _uuid
    data = await follow_svc.follow(db, user, _uuid.UUID(user_id))
    return {"code": 0, "data": data}


@router.delete("/users/{user_id}/follow")
async def unfollow_user(
    user_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "admin")),
):
    import uuid as _uuid
    data = await follow_svc.unfollow(db, user, _uuid.UUID(user_id))
    return {"code": 0, "data": data}


# ---- 个人主页 ----


def _to_uuid(user_id: str):
    import uuid as _uuid
    return _uuid.UUID(user_id)


@router.get("/users/{user_id}/profile")
async def get_user_profile(
    user_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    data = await profile_svc.get_profile(db, _to_uuid(user_id), viewer)
    if data is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 0, "data": data}


@router.get("/users/{user_id}/following")
async def get_user_following(
    user_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    items = await profile_svc.list_following(db, _to_uuid(user_id), viewer)
    return {"code": 0, "data": {"items": items}}


@router.get("/users/{user_id}/followers")
async def get_user_followers(
    user_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    items = await profile_svc.list_followers(db, _to_uuid(user_id), viewer)
    return {"code": 0, "data": {"items": items}}


@router.get("/users/{user_id}/posts")
async def get_user_posts(
    user_id: str = Path(..., pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
    cursor: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    items, next_cursor, has_more = await user_posts(db, _to_uuid(user_id), viewer, cursor)
    return {"code": 0, "data": {"items": items, "next_cursor": next_cursor, "has_more": has_more}}
