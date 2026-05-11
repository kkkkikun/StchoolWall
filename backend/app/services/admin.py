from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.report import Report
from app.models.user import User


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
    db: AsyncSession, report_id: int, action: str
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
    elif action == "ban_user":
        report.status = "resolved"
        if post:
            post.status = -1
            user_result = await db.execute(select(User).where(User.id == post.user_id))
            author = user_result.scalar_one_or_none()
            if author:
                author.status = 0

    await db.commit()
    return {"report_id": report.id, "status": report.status}


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
