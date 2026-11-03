"""互动业务逻辑：评论 / 点赞 / 收藏 / 浏览足迹 / 个人统计。

计数策略：点赞/评论写操作同步维护 posts.like_count / comment_count
（check-then-write，复合主键兜底防重复），列表页直接读冗余字段。
"""
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Comment, Favorite, Footprint, Like
from app.models.post import Post
from app.models.notification import Notification
from app.services.jobs import enqueue_job
from app.services.blocks import require_interaction, visible_author
from app.models.user import User
from app.services.notification import create_notification


# ---- 通用 ----


async def _get_post(db: AsyncSession, post_id: int, for_update: bool = False, actor_id=None, viewer: User | None = None) -> Post | None:
    """互动目标帖：必须存在且 status==1（封禁/待审帖不可被点赞评论收藏）。

    互动路径一律不锁 posts 行（for_update 只留给审核等低频路径）：计数用原子
    自增语句维护，行锁只持续到该语句结束，不再把热点帖变成串行点。
    """
    statement = select(Post).where(Post.id == post_id, Post.status == 1, visible_author(Post.user_id, viewer))
    if for_update:
        statement = statement.with_for_update()
    r = await db.execute(statement)
    post = r.scalar_one_or_none()
    if post and actor_id is not None:
        await require_interaction(db, actor_id, post.user_id)
    return post


async def _bump_like_count(db: AsyncSession, post_id: int, delta: int) -> int:
    """原子调整 posts.like_count 并返回新值（不越界、不丢更新）。

    不带 status 条件：计数必须与 likes 表一致，帖子被隐藏也不应让计数漂移。
    """
    stmt = (
        update(Post)
        .where(Post.id == post_id)
        .values(like_count=func.greatest(func.coalesce(Post.like_count, 0) + delta, 0))
        .returning(Post.like_count)
    )
    value = (await db.execute(stmt)).scalar_one_or_none()
    if value is None:
        value = (await db.execute(select(Post.like_count).where(Post.id == post_id))).scalar_one_or_none()
    return int(value or 0)


# ---- 点赞（幂等） ----


async def like_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id, actor_id=user.id)
    if not post:
        return None

    # 幂等插入：唯一约束兜底，避免 check-then-insert 并发撞出 IntegrityError
    inserted = (
        await db.execute(
            pg_insert(Like)
            .values(user_id=user.id, post_id=post_id)
            .on_conflict_do_nothing(constraint="likes_pkey")
        )
    ).rowcount == 1

    if inserted:
        # 原子自增，避免 read-modify-write 并发丢更新
        like_count = await _bump_like_count(db, post_id, 1)
        if post.user_id != user.id:
            db.add(Notification(user_id=post.user_id, actor_id=user.id, type="like", post_id=post_id))
        await db.commit()
    else:
        await db.commit()
        like_count = int(
            (await db.execute(select(Post.like_count).where(Post.id == post_id))).scalar_one_or_none() or 0
        )
    return {"liked": True, "like_count": like_count}


async def unlike_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id, actor_id=user.id)
    if not post:
        return None

    deleted = (
        await db.execute(
            delete(Like).where(Like.user_id == user.id, Like.post_id == post_id)
        )
    ).rowcount == 1

    if deleted:
        # 原子自减且不越过 0
        like_count = await _bump_like_count(db, post_id, -1)
    else:
        like_count = int(
            (await db.execute(select(Post.like_count).where(Post.id == post_id))).scalar_one_or_none() or 0
        )
    await db.commit()
    return {"liked": False, "like_count": like_count}


# ---- 评论 ----


def _comment_dict(c: Comment, nickname: str, avatar_url: str | None = None,
                  comment_count: int | None = None) -> dict:
    d = {
        "id": c.id,
        "post_id": c.post_id,
        "user_id": str(c.user_id),
        "content": c.content,
        "status": c.status,
        "user": {"nickname": nickname, "avatar_url": avatar_url},
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
    if comment_count is not None:
        d["comment_count"] = comment_count
    return d


async def create_comment(db: AsyncSession, user: User, post_id: int, content: str) -> dict | None:
    """发评论（同步本地词检：hard 拒 / gray 待审 / clean 即见）。

    - hard：抛 ValueError（路由转 400），评论不创建，审核记录 post_id=被评帖
    - gray：status=0 待审——不计数不通知，过审（admin）时补计数与通知
    - clean：status=1 即见，计数 + 通知帖子作者（不通知自己）
    """
    post = await _get_post(db, post_id, actor_id=user.id)
    if not post:
        return None

    from app.services.moderation_record import add_moderation_record
    from app.services.sensitive_word import load_active_words
    from app.utils.local_rules import check_text_local

    local_r, matched = check_text_local(content, await load_active_words(db))
    if local_r.verdict == "reject":
        add_moderation_record(db, post_id, "rule", local_r, matched=matched or None)
        await db.commit()
        raise ValueError("评论包含违规内容，无法提交")

    status = 1 if user.role == "admin" and local_r.verdict == "pass" else 0
    c = Comment(post_id=post_id, user_id=user.id, content=content, status=status)
    db.add(c)
    await db.flush()
    add_moderation_record(db, post_id, "rule", local_r, matched=matched or None, comment_id=c.id)
    if status == 0:
        await enqueue_job(db, "moderate_comment", {"comment_id": c.id}, f"comment:{c.id}")
    else:
        # 原子自增，不带 status 条件：计数必须与 comments 表一致
        await db.execute(
            update(Post).where(Post.id == post_id)
            .values(comment_count=func.coalesce(Post.comment_count, 0) + 1)
        )
        if post.user_id != user.id:
            db.add(Notification(user_id=post.user_id, actor_id=user.id, type="comment",
                                post_id=post_id, comment_id=c.id))
    await db.commit()
    await db.refresh(c)
    await db.refresh(post)
    return _comment_dict(c, user.nickname, user.avatar_url, post.comment_count)


async def list_comments(
    db: AsyncSession, post_id: int, cursor: int | None = None, limit: int = 20, viewer: User | None = None
) -> tuple[list[dict], int | None, bool]:
    conds = [Comment.post_id == post_id, Comment.status == 1, visible_author(Comment.user_id, viewer)]
    if cursor:
        conds.append(Comment.id < cursor)
    stmt = (
        select(Comment, User)
        .join(User, Comment.user_id == User.id)
        .where(*conds)
        .order_by(Comment.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_comment_dict(c, u.nickname, u.avatar_url) for c, u in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def delete_comment(db: AsyncSession, user: User, comment_id: int) -> bool | None:
    """返回 None=未找到(404)，False=无权(403)，True=成功。"""
    c = (await db.execute(select(Comment).where(Comment.id == comment_id).with_for_update())).scalar_one_or_none()
    if not c:
        return None
    if str(c.user_id) != str(user.id) and user.role != "admin":
        return False
    was_public = c.status == 1
    c.status = -1
    # A pending or already deleted comment was never included in the counter.
    if was_public:
        await db.execute(
            update(Post)
            .where(
                Post.id == c.post_id,
                func.coalesce(Post.comment_count, 0) > 0,
            )
            .values(comment_count=func.coalesce(Post.comment_count, 0) - 1)
        )
    await db.commit()
    return True


# ---- 收藏（幂等） ----


async def favorite_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id, actor_id=user.id)
    if not post:
        return None

    # 幂等插入：唯一约束兜底，避免并发重复收藏
    inserted = (
        await db.execute(
            pg_insert(Favorite)
            .values(user_id=user.id, post_id=post_id)
            .on_conflict_do_nothing(constraint="favorites_pkey")
        )
    ).rowcount == 1

    if inserted and post.user_id != user.id:
        db.add(Notification(user_id=post.user_id, actor_id=user.id, type="favorite", post_id=post_id))
    await db.commit()
    return {"favorited": True}


async def unfavorite_post(db: AsyncSession, user: User, post_id: int) -> dict | None:
    post = await _get_post(db, post_id, actor_id=user.id)
    if not post:
        return None
    await db.execute(
        delete(Favorite).where(Favorite.user_id == user.id, Favorite.post_id == post_id)
    )
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
    conds = [Favorite.user_id == user.id, Post.status == 1, visible_author(Post.user_id, user)]
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
    conds = [Like.user_id == user.id, Post.status == 1, visible_author(Post.user_id, user)]
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
    await db.execute(
        pg_insert(Footprint).values(user_id=user.id, post_id=post_id)
        .on_conflict_do_update(constraint="uq_footprints_user_post", set_={"viewed_at": func.now()})
    )
    await db.commit()


async def list_footprints(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    conds = [Footprint.user_id == user.id, Post.status == 1, visible_author(Post.user_id, user)]
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
