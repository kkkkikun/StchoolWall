from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

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
    return {"report_id": report.id, "status": report.status}


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
) -> tuple[list[dict], int | None, bool]:
    """admin 帖子列表：全量（含待审/封禁/广告），q 模糊搜索，游标分页。"""
    conditions = []
    if status is not None:
        conditions.append(Post.status == status)
    if q:
        conditions.append(Post.content.ilike(f"%{q}%"))
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

    items = [{
        "id": p.id,
        "post_type": p.post_type,
        "category": p.category,
        "content": p.content[:100],
        "images_count": len(p.images or []),
        "price": float(p.price) if p.price else None,
        "status": p.status,
        "is_pinned": bool(p.is_pinned),
        "author": {"nickname": nick, "id": str(p.user_id)},
        "like_count": p.like_count or 0,
        "comment_count": p.comment_count or 0,
        "view_count": p.view_count or 0,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p, nick in rows]

    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


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
) -> tuple[list[dict], str | None, bool]:
    conditions = []
    if cursor:
        conditions.append(User.id < cursor)

    stmt = (
        select(User)
        .where(*conditions)
        .order_by(User.created_at.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    has_more = len(users) > limit
    users = users[:limit]

    items = []
    for u in users:
        items.append({
            "id": str(u.id),
            "nickname": u.nickname,
            "role": u.role,
            "is_verified": u.is_verified,
            "student_id": u.student_id,
            "real_name": u.real_name,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    next_cursor = str(users[-1].id) if has_more and users else None
    return items, next_cursor, has_more


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
