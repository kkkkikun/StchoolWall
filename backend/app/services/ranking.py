"""热门用户榜：按正常帖子收到的点赞总数排序（消息页横滑榜数据源）。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.user import User
from app.services.blocks import visible_author


async def hot_users(db: AsyncSession, limit: int = 5, viewer: User | None = None) -> list[dict]:
    """Top 用户：heat = 其 status=1、非广告帖的 like_count 之和（全量口径）。

    内连接天然过滤掉没发过帖的用户；广告不计入热度。
    """
    heat = func.coalesce(func.sum(Post.like_count), 0)
    stmt = (
        select(User.id, User.nickname, User.avatar_url, heat.label("heat"))
        .join(Post, (Post.user_id == User.id) & (Post.status == 1) & (Post.post_type != "advertisement"))
        .where(User.status == 1, visible_author(User.id, viewer))
        .group_by(User.id, User.nickname, User.avatar_url)
        .order_by(heat.desc(), User.id.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {"id": str(uid), "nickname": nick, "avatar_url": avatar, "heat": int(h or 0)}
        for uid, nick, avatar, h in rows
    ]
