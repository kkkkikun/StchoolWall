from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Comment, Like
from app.models.post import Post
from app.models.report import Report
from app.models.user import User
from app.services.notification import create_system_notification


async def list_reports(
    db: AsyncSession,
    status: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
) -> tuple[list[dict], int | None, bool]:
    conditions = []
    if status:
        conditions.append(Report.status == status)
    if cursor:
        conditions.append(Report.id < cursor)

    stmt = (
        select(Report, Post, User)
        .join(Post, Report.post_id == Post.id)
        .join(User, Report.reporter_id == User.id)
        .where(*conditions)
        .order_by(Report.created_at.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = []
    for report, post, reporter in rows:
        items.append({
            "id": report.id,
            "post_id": report.post_id,
            "post_content": post.content[:100],
            "post_status": post.status,
            "reporter": {"id": str(reporter.id), "nickname": reporter.nickname},
            "reason": report.reason,
            "description": report.description,
            "status": report.status,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        })

    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def handle_report(
    db: AsyncSession, report_id: int, action: str, admin_id=None
) -> dict | None:
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        return None

    if report.status != "pending":
        return {"error": "该举报已处理"}

    # Get the post and author
    post_result = await db.execute(select(Post).where(Post.id == report.post_id))
    post = post_result.scalar_one_or_none()

    if action == "dismiss":
        report.status = "dismissed"
    elif action == "ban_post":
        report.status = "resolved"
        if post:
            post.status = -1
            await create_system_notification(db, post.user_id, "moderation", post_id=post.id)
    elif action == "ban_user":
        report.status = "resolved"
        if post:
            post.status = -1
            await create_system_notification(db, post.user_id, "moderation", post_id=post.id)
            user_result = await db.execute(select(User).where(User.id == post.user_id))
            author = user_result.scalar_one_or_none()
            if author:
                author.status = 0

    # 处理留痕
    if admin_id is not None:
        report.handled_by = admin_id
    from sqlalchemy.sql import func as sa_func
    report.handled_at = sa_func.now()

    await db.commit()
    return {"report_id": report.id, "status": report.status, "post_id": report.post_id}


# ---- 帖子管理（待审队列 / 封禁恢复） ----

# admin 允许的状态流转：{当前状态: {允许的目标状态}}
POST_STATUS_TRANSITIONS = {
    0: {1, -1},   # 待审 → 过审 / 拒审
    1: {-1},      # 正常 → 封禁
    -1: {1},      # 封禁 → 恢复
}


async def list_posts_admin(
    db: AsyncSession,
    status: int | None = None,
    q: str | None = None,
    cursor: int | None = None,
    limit: int = 20,
    *,
    post_type: str | None = None,
    category: str | None = None,
    author_id: str | None = None,
    time_start=None,
    time_end=None,
    page: int | None = None,
    page_size: int = 20,
) -> tuple[list[dict], int | None, bool, int | None]:
    """admin 帖子列表：全量（含待审/封禁/广告），多条件筛选。

    - cursor 模式（旧，小程序兼容）：返回 (items, next_cursor, has_more, None)
    - page 模式（Web 后台）：返回 (items, None, False, total)
    """
    conditions = []
    if status is not None:
        conditions.append(Post.status == status)
    if q:
        conditions.append(Post.content.ilike(f"%{q}%"))
    if post_type:
        conditions.append(Post.post_type == post_type)
    if category:
        conditions.append(Post.category == category)
    if author_id:
        conditions.append(Post.user_id == author_id)
    if time_start:
        conditions.append(Post.created_at >= time_start)
    if time_end:
        conditions.append(Post.created_at <= time_end)

    def _row_to_item(p, nick):
        return {
            "id": p.id,
            "post_type": p.post_type,
            "category": p.category,
            "content": p.content[:100],
            "images_count": len(p.images or []),
            "price": float(p.price) if p.price else None,
            "status": p.status,
            "is_pinned": bool(p.is_pinned),
            "is_featured": bool(p.is_featured),
            "author": {"nickname": nick, "id": str(p.user_id)},
            "like_count": p.like_count or 0,
            "comment_count": p.comment_count or 0,
            "view_count": p.view_count or 0,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    if page is not None:
        # page 模式：offset/limit + 总数
        total = await db.scalar(
            select(func.count()).select_from(Post).where(*conditions)
        ) or 0
        stmt = (
            select(Post, User.nickname)
            .join(User, Post.user_id == User.id)
            .where(*conditions)
            .order_by(Post.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).all()
        return [_row_to_item(p, nick) for p, nick in rows], None, False, total

    # cursor 模式（旧）
    if cursor:
        conditions.append(Post.id < cursor)
    stmt = (
        select(Post, User.nickname)
        .join(User, Post.user_id == User.id)
        .where(*conditions)
        .order_by(Post.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_row_to_item(p, nick) for p, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more, None


async def admin_update_post(db: AsyncSession, post_id: int, data: dict) -> Post | None:
    """admin 编辑帖子（content/category/images/price 局部更新）。"""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        return None
    for field, value in data.items():
        setattr(post, field, value)
    await db.commit()
    await db.refresh(post)
    return post


async def admin_batch_post_status(db: AsyncSession, post_ids: list[int], new_status: int) -> dict:
    """批量状态流转：逐个走状态机，返回 {succeeded, failed:[{id, reason}]}。"""
    succeeded: list[int] = []
    failed: list[dict] = []
    for pid in post_ids:
        result = await admin_update_post_status(db, pid, new_status)
        if result is None:
            failed.append({"id": pid, "reason": "帖子不存在"})
        elif result == "invalid":
            failed.append({"id": pid, "reason": "非法的状态流转"})
        else:
            succeeded.append(pid)
    return {"succeeded": succeeded, "failed": failed}


async def admin_update_post_status(
    db: AsyncSession, post_id: int, new_status: int
) -> Post | None | str:
    """admin 状态机流转；非法流转返回 'invalid'，不存在返回 None。"""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        return None

    allowed = POST_STATUS_TRANSITIONS.get(post.status, set())
    if new_status not in allowed:
        return "invalid"

    old_status = post.status
    post.status = new_status
    # 拒审/封禁（→ -1）通知作者；恢复/过审不通知
    if new_status == -1 and old_status in (0, 1):
        await create_system_notification(db, post.user_id, "moderation", post_id=post.id)
    await db.commit()
    await db.refresh(post)
    return post


async def admin_stats(db: AsyncSession) -> dict:
    """管理看板聚合。"""
    pending_posts = await db.scalar(
        select(func.count()).select_from(Post).where(Post.status == 0)
    ) or 0
    pending_reports = await db.scalar(
        select(func.count()).select_from(Report).where(Report.status == "pending")
    ) or 0
    total_posts = await db.scalar(select(func.count()).select_from(Post)) or 0
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    frozen_users = await db.scalar(
        select(func.count()).select_from(User).where(User.status == 0)
    ) or 0
    posts_today = await db.scalar(
        select(func.count()).select_from(Post)
        .where(Post.created_at >= func.now() - text("interval '1 day'"))
    ) or 0
    return {
        "pending_posts": pending_posts,
        "pending_reports": pending_reports,
        "total_posts": total_posts,
        "total_users": total_users,
        "frozen_users": frozen_users,
        "posts_today": posts_today,
    }


async def list_users(
    db: AsyncSession,
    cursor: str | None = None,
    limit: int = 20,
    *,
    q: str | None = None,
    role: str | None = None,
    is_verified: bool | None = None,
    status: int | None = None,
    time_start=None,
    time_end=None,
    page: int | None = None,
    page_size: int = 20,
) -> tuple[list[dict], str | None, bool, int | None]:
    """用户列表：q 命中 nickname/student_id/real_name 任一 ILIKE。

    cursor 模式返回 (items, next_cursor, has_more, None)；page 模式返回 (items, None, False, total)。
    """
    conditions = []
    if q:
        like = f"%{q}%"
        conditions.append(
            (User.nickname.ilike(like))
            | (User.student_id.ilike(like))
            | (User.real_name.ilike(like))
        )
    if role:
        conditions.append(User.role == role)
    if is_verified is not None:
        conditions.append(User.is_verified.is_(is_verified))
    if status is not None:
        conditions.append(User.status == status)
    if time_start:
        conditions.append(User.created_at >= time_start)
    if time_end:
        conditions.append(User.created_at <= time_end)

    def _u_to_item(u):
        return {
            "id": str(u.id),
            "nickname": u.nickname,
            "role": u.role,
            "is_verified": u.is_verified,
            "student_id": u.student_id,
            "real_name": u.real_name,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }

    if page is not None:
        total = await db.scalar(
            select(func.count()).select_from(User).where(*conditions)
        ) or 0
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        users = (await db.execute(stmt)).scalars().all()
        return [_u_to_item(u) for u in users], None, False, total

    # cursor 模式（旧）
    if cursor:
        conditions.append(User.id < cursor)
    stmt = (
        select(User)
        .where(*conditions)
        .order_by(User.id.desc())
        .limit(limit + 1)
    )
    users = (await db.execute(stmt)).scalars().all()
    has_more = len(users) > limit
    users = users[:limit]
    items = [_u_to_item(u) for u in users]
    next_cursor = str(users[-1].id) if has_more and users else None
    return items, next_cursor, has_more, None


async def update_user_role(
    db: AsyncSession, user_id: str, new_role: str, actor_id: str
) -> User | None | str:
    """修改用户角色；legacy 管理员不能降自己（防锁死自己的管理入口）。"""
    if str(user_id) == str(actor_id):
        return "self_demote"
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.role = new_role
    await db.commit()
    await db.refresh(user)
    return user


async def admin_user_detail(db: AsyncSession, user_id: str) -> dict | None:
    """用户详情：基础字段 + 内容计数 + 最近 10 帖 + 被举报次数。"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    posts_count = await db.scalar(
        select(func.count()).select_from(Post)
        .where(Post.user_id == user.id, Post.status != -2)
    ) or 0
    comments_count = await db.scalar(
        select(func.count()).select_from(Comment)
        .where(Comment.user_id == user.id, Comment.status == 1)
    ) or 0
    likes_received = await db.scalar(
        select(func.count()).select_from(Like)
        .join(Post, Like.post_id == Post.id)
        .where(Post.user_id == user.id)
    ) or 0
    reported_count = await db.scalar(
        select(func.count()).select_from(Report)
        .join(Post, Report.post_id == Post.id)
        .where(Post.user_id == user.id)
    ) or 0
    recent = (await db.execute(
        select(Post).where(Post.user_id == user.id, Post.status != -2)
        .order_by(Post.id.desc()).limit(10)
    )).scalars().all()

    return {
        "id": str(user.id),
        "nickname": user.nickname,
        "role": user.role,
        "is_verified": user.is_verified,
        "student_id": user.student_id,
        "real_name": user.real_name,
        "wechat_id": user.wechat_id,
        "avatar_url": user.avatar_url,
        "status": user.status,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "posts_count": posts_count,
        "comments_count": comments_count,
        "likes_received": likes_received,
        "reported_count": reported_count,
        "recent_posts": [{
            "id": p.id, "content": p.content[:50], "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        } for p in recent],
    }


async def update_user_status(
    db: AsyncSession, user_id: str, new_status: int
) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return None

    user.status = new_status
    await db.commit()
    await db.refresh(user)
    return user
