"""互动业务逻辑：评论 / 点赞 / 收藏 / 浏览足迹 / 个人统计。

计数策略：点赞/评论写操作同步维护 posts.like_count / comment_count
（check-then-write，复合主键兜底防重复），列表页直接读冗余字段。
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Comment, Favorite, Footprint, Like
from app.models.post import Post
from app.models.user import User
from app.services.notification import create_notification


# ---- 通用 ----


async def _get_post(db: AsyncSession, post_id: int) -> Post | None:
    r = await db.execute(select(Post).where(Post.id == post_id))
    return r.scalar_one_or_none()


async def _is_liked(db: AsyncSession, user_id: uuid.UUID, post_id: int) -> bool:
    r = await db.execute(select(Like).where(Like.user_id == user_id, Like.post_id == post_id))
    return r.scalar_one_or_none() is not None


async def _is_favorited(db: AsyncSession, user_id: uuid.UUID, post_id: int) -> bool:
    r = await db.execute(select(Favorite).where(Favorite.user_id == user_id, Favorite.post_id == post_id))
    return r.scalar_one_or_none() is not None


# ---- 点赞（幂等） ----


async def like_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id)
    if not post:
        return None
    if not await _is_liked(db, user.id, post_id):
        db.add(Like(user_id=user.id, post_id=post_id))
        post.like_count = (post.like_count or 0) + 1
        await db.commit()
        # 通知帖子作者（不通知自己）
        await create_notification(db, post.user_id, user.id, "like", post_id=post_id)
    await db.refresh(post)
    return {"liked": True, "like_count": post.like_count}


async def unlike_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id)
    if not post:
        return None
    like = (await db.execute(
        select(Like).where(Like.user_id == user.id, Like.post_id == post_id)
    )).scalar_one_or_none()
    if like:
        await db.delete(like)
        if post.like_count and post.like_count > 0:
            post.like_count = post.like_count - 1
        await db.commit()
    await db.refresh(post)
    return {"liked": False, "like_count": post.like_count}


# ---- 评论 ----


def _comment_dict(c: Comment, nickname: str, comment_count: int | None = None) -> dict:
    d = {
        "id": c.id,
        "post_id": c.post_id,
        "user_id": str(c.user_id),
        "content": c.content,
        "user": {"nickname": nickname},
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if comment_count is not None:
        d["comment_count"] = comment_count
    return d


async def create_comment(db: AsyncSession, user: User, post_id: int, content: str) -> dict | None:
    post = await _get_post(db, post_id)
    if not post:
        return None
    c = Comment(post_id=post_id, user_id=user.id, content=content)
    db.add(c)
    await db.flush()
    post.comment_count = (post.comment_count or 0) + 1
    await db.commit()
    await db.refresh(c)
    await db.refresh(post)
    # 通知帖子作者（不通知自己）
    await create_notification(db, post.user_id, user.id, "comment", post_id=post.id, comment_id=c.id)
    return _comment_dict(c, user.nickname, post.comment_count)


async def list_comments(
    db: AsyncSession, post_id: int, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    conds = [Comment.post_id == post_id, Comment.status == 1]
    if cursor:
        conds.append(Comment.id < cursor)
    stmt = (
        select(Comment, User.nickname)
        .join(User, Comment.user_id == User.id)
        .where(*conds)
        .order_by(Comment.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_comment_dict(c, nick) for c, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def delete_comment(db: AsyncSession, user: User, comment_id: int) -> bool | None:
    """返回 None=未找到(404)，False=无权(403)，True=成功。"""
    c = (await db.execute(select(Comment).where(Comment.id == comment_id))).scalar_one_or_none()
    if not c:
        return None
    if str(c.user_id) != str(user.id) and user.role != "admin":
        return False
    c.status = -1  # 软删除
    post = await _get_post(db, c.post_id)
    if post and post.comment_count and post.comment_count > 0:
        post.comment_count = post.comment_count - 1
    await db.commit()
    return True


# ---- 收藏（幂等） ----


async def favorite_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id)
    if not post:
        return None
    if not await _is_favorited(db, user.id, post_id):
        db.add(Favorite(user_id=user.id, post_id=post_id))
        await db.commit()
        # 通知帖子作者（不通知自己）；type=favorite，消息页互动聚合展示
        await create_notification(db, post.user_id, user.id, "favorite", post_id=post_id)
    return {"favorited": True}


async def unfavorite_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id)
    if not post:
        return None
    fav = (await db.execute(
        select(Favorite).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
    )).scalar_one_or_none()
    if fav:
        await db.delete(fav)
        await db.commit()
    return {"favorited": False}


def _post_brief(post: Post, nickname: str) -> dict:
    return {
        "id": post.id,
        "post_type": post.post_type,
        "content": post.content,
        "images": post.images or [],
        "price": float(post.price) if post.price else None,
        "status": post.status,
        "user": {"nickname": nickname},
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "view_count": post.view_count or 0,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


async def list_favorites(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    """收藏列表（按收藏时间倒序，游标用 Favorite.created_at 不可靠，改用 post.id）。"""
    conds = [Favorite.user_id == user.id, Post.status == 1]
    if cursor:
        conds.append(Favorite.post_id < cursor)
    stmt = (
        select(Post, User.nickname)
        .join(Favorite, Favorite.post_id == Post.id)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        # 复合主键无自增 id；post_id 对 (user, post) 唯一，作稳定排序键与游标
        .order_by(Favorite.post_id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_post_brief(p, nick) for p, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def list_my_likes(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    """我点赞过的帖子（按点赞时间≈post_id 倒序）。"""
    conds = [Like.user_id == user.id, Post.status == 1]
    if cursor:
        conds.append(Like.post_id < cursor)
    stmt = (
        select(Post, User.nickname)
        .join(Like, Like.post_id == Post.id)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Like.post_id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_post_brief(p, nick) for p, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def list_my_comments(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    """我发表过的评论（含所属帖子摘要，软删除除外）。"""
    conds = [Comment.user_id == user.id, Comment.status == 1]  # 软删除(−1)不显示
    if cursor:
        conds.append(Comment.id < cursor)
    stmt = (
        select(Comment, Post.content, User.nickname)
        .join(Post, Comment.post_id == Post.id)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Comment.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        {
            "id": c.id,
            "post_id": c.post_id,
            "content": c.content,
            "post_excerpt": (pc or "")[:50],
            "post_author": nick,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c, pc, nick in rows
    ]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


# ---- 足迹 ----


async def record_footprint(db: AsyncSession, user: User, post_id: int) -> None:
    """记录浏览足迹：同一 (user,post) 已有则更新 viewed_at，否则新增（应用级检查）。"""
    fp = (await db.execute(
        select(Footprint).where(Footprint.user_id == user.id, Footprint.post_id == post_id)
    )).scalar_one_or_none()
    if fp:
        from sqlalchemy import update
        await db.execute(
            update(Footprint).where(Footprint.id == fp.id).values(viewed_at=func.now())
        )
    else:
        db.add(Footprint(user_id=user.id, post_id=post_id))
    await db.commit()


async def list_footprints(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    conds = [Footprint.user_id == user.id, Post.status == 1]
    if cursor:
        conds.append(Footprint.id < cursor)
    stmt = (
        select(Post, User.nickname, Footprint.id.label("fp_id"))
        .join(Post, Footprint.post_id == Post.id)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Footprint.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_post_brief(p, nick) for p, nick, _fp_id in rows]
    next_cursor = rows[-1][2] if has_more and rows else None
    return items, next_cursor, has_more


# ---- 统计 ----


async def get_stats(db: AsyncSession, user: User) -> dict:
    posts_count = await db.scalar(
        select(func.count()).select_from(Post)
        .where(Post.user_id == user.id, Post.status != -2)
    ) or 0
    comments_count = await db.scalar(
        select(func.count()).select_from(Comment)
        .where(Comment.user_id == user.id, Comment.status == 1)
    ) or 0
    favorites_count = await db.scalar(
        select(func.count()).select_from(Favorite).where(Favorite.user_id == user.id)
    ) or 0
    footprints_count = await db.scalar(
        select(func.count()).select_from(Footprint).where(Footprint.user_id == user.id)
    ) or 0
    return {
        "posts_count": posts_count,
        "comments_count": comments_count,
        "favorites_count": favorites_count,
        "footprints_count": footprints_count,
    }
