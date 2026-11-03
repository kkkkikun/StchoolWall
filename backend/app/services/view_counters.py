"""浏览计数异步聚合。

瓶颈背景（docs/production/capacity.md）：详情页浏览数自增与点赞路径的
`SELECT ... FOR UPDATE` 争热点帖同一行，PostgreSQL 记录到同一 tuple 上最长
38 个进程的锁等待队列，burst 场景读 p95 2743.72ms / 写 p95 4063.85ms。

本模块把浏览计数从「同步写 posts 行」改为「写 post_view_counters + worker
周期性折叠回 posts.view_count」：

- 读路径只碰 post_view_counters，不再锁 posts 行，热点帖详情浏览与点赞/评论
  不再在同一个 tuple 上串行；
- 折叠在独立小事务里逐帖进行（先 FOR UPDATE 取增量，再原子自增 posts.view_count
  并清零），单个事务只锁一行、持锁时间在毫秒级；
- 详情接口返回「已聚合值 + 待聚合增量」，取自同一条语句的一致快照。
"""
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.view_counter import PostViewCounter


async def record_post_view(db: AsyncSession, post_id: int) -> int:
    """记录一次浏览，返回该帖当前待聚合的浏览增量。

    计数用 `ON CONFLICT DO UPDATE` 原子自增，并发浏览不会丢增量。
    """
    stmt = (
        pg_insert(PostViewCounter)
        .values(post_id=post_id, views=1)
        .on_conflict_do_update(
            index_elements=[PostViewCounter.post_id],
            set_={"views": PostViewCounter.views + 1, "updated_at": func.now()},
        )
        .returning(PostViewCounter.views)
    )
    return int((await db.execute(stmt)).scalar_one())


async def current_view_count(db: AsyncSession, post_id: int) -> int:
    """浏览数 = 已聚合的 posts.view_count + 待聚合增量（单条语句内一致快照）。"""
    stmt = (
        select(func.coalesce(Post.view_count, 0) + func.coalesce(PostViewCounter.views, 0))
        .select_from(Post)
        .outerjoin(PostViewCounter, PostViewCounter.post_id == Post.id)
        .where(Post.id == post_id)
    )
    return int((await db.execute(stmt)).scalar_one())


async def flush_post_view_counters(db: AsyncSession, limit: int = 200) -> int:
    """把待聚合的浏览增量折叠进 posts.view_count，返回折叠的帖子数。

    逐帖一个小事务：先锁住该帖的计数行取出增量，再原子自增 posts.view_count
    并把计数行清零；读路径的并发自增要么在本事务之前完成（被一起折叠）、
    要么在提交后完成（重新自增），不会丢增量。
    """
    post_ids = (
        await db.execute(
            select(PostViewCounter.post_id)
            .where(PostViewCounter.views > 0)
            .order_by(PostViewCounter.updated_at)
            .limit(limit)
        )
    ).scalars().all()

    folded = 0
    for post_id in post_ids:
        row = (
            await db.execute(
                select(PostViewCounter)
                .where(PostViewCounter.post_id == post_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None or not row.views:
            await db.rollback()
            continue
        await db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(view_count=func.coalesce(Post.view_count, 0) + row.views)
        )
        row.views = 0
        await db.commit()
        folded += 1
    return folded
