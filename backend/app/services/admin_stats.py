"""管理看板趋势：按日聚合（Asia/Shanghai 时区切日）。

注意：时间边界一律用 SQL 端 func.now() 或带时区的 datetime——
naive datetime 经 asyncpg 参数化会被按本地时区偏移，导致过滤条件错位。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Comment, Footprint, Like
from app.models.post import Post
from app.models.user import User

MAX_DAYS = 90
SHANGHAI_TZ = timezone(timedelta(hours=8))


def _day_expr(column):
    """列 → 上海时区的 YYYY-MM-DD（分组键）。"""
    return func.to_char(
        func.date_trunc("day", func.timezone("Asia/Shanghai", column)), "YYYY-MM-DD"
    )


async def _daily_counts(db: AsyncSession, column, days: int) -> dict[str, int]:
    """近 N 天按日 count（下界带时区，上界用 SQL now()）。"""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(_day_expr(column).label("d"), func.count())
        .where(column >= start, column < func.now())
        .group_by("d")
    )
    rows = (await db.execute(stmt)).all()
    return {d: c for d, c in rows}


async def _daily_active_users(db: AsyncSession, days: int) -> dict[str, int]:
    """DAU（估算）：按足迹表 distinct user 聚合（足迹在浏览帖子时写入）。"""
    start = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(
            _day_expr(Footprint.viewed_at).label("d"),
            func.count(func.distinct(Footprint.user_id)),
        )
        .where(Footprint.viewed_at >= start, Footprint.viewed_at < func.now())
        .group_by("d")
    )
    rows = (await db.execute(stmt)).all()
    return {d: c for d, c in rows}


async def admin_stats_trends(db: AsyncSession, days: int = 14) -> dict:
    """近 N 天趋势：posts/comments/likes/new_users/active_users 按日序列（补零对齐）。"""
    days = max(1, min(days, MAX_DAYS))

    posts = await _daily_counts(db, Post.created_at, days)
    comments = await _daily_counts(db, Comment.created_at, days)
    likes = await _daily_counts(db, Like.created_at, days)
    new_users = await _daily_counts(db, User.created_at, days)
    active = await _daily_active_users(db, days)

    # 日期序列按上海时区生成，缺日补零
    sh_today = datetime.now(SHANGHAI_TZ).date()
    series = []
    for i in range(days - 1, -1, -1):
        d = (sh_today - timedelta(days=i)).isoformat()
        series.append({
            "date": d,
            "posts": posts.get(d, 0),
            "comments": comments.get(d, 0),
            "likes": likes.get(d, 0),
            "new_users": new_users.get(d, 0),
            "active_users": active.get(d, 0),
        })
    return {"days": days, "series": series}
