"""推荐流热度分的榜单预计算。

瓶颈背景（docs/production/capacity.md）：推荐流 `/api/v1/posts`（不带 order）
按含 `now()` 的热度分排序，PostgreSQL 无法用表达式索引直接排序，只能
Parallel Seq Scan → Sort（隔离环境实测单次 662.276ms）。

本模块把热度分按固定周期在 worker 里算好落到 `post_hot_scores` 表，查询只做
`(score, post_id)` 索引扫描 + 键集分页。**热度分公式本身不变**，推荐结果的可
解释性不变；榜单过期（worker 未运行）时读接口退回实时计算，结果始终正确。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hot_score import PostHotScore, PostHotScoreState
from app.models.post import Post

# 预计算周期（秒）与榜单过期判定（秒）：worker 每分钟刷新一次，超过 5 分钟未刷新
# 视为 worker 异常，读接口退回实时计算的降级路径。
HOT_SCORE_REFRESH_SECONDS = 60
HOT_SCORE_STALE_SECONDS = 300
STATE_ROW_ID = 1


def hot_score_expr(model=Post, reference: datetime | None = None):
    """推荐热度分：互动加权 / 时间衰减（Reddit 式）。

    - 分子 +1 保底：零互动新帖不被永久淹没，无互动时退化为近似时间序
    - 分母 (发布小时 + 2)^1.2：好帖大约存活 1~2 天后自然沉底
    - 权重与热帖榜（hot_posts）同源：like*3 + comment*2 + view*0.2
    - 计数列的 NULL 按 0 计（与列默认值一致），避免预计算榜单写入 NULL

    `reference` 给定时按该时刻计算时间衰减：预计算榜单用它保持同源口径
    （榜单内的分与实时降级路径的分仍可比）。
    """
    now_expr = func.now() if reference is None else literal(reference, type_=DateTime(timezone=True))
    hours = func.extract("epoch", now_expr - model.created_at) / 3600.0
    engagement = (
        func.coalesce(model.like_count, 0) * 3
        + func.coalesce(model.comment_count, 0) * 2
        + func.coalesce(model.view_count, 0) * 0.2
        + 1
    )
    return engagement / func.power(hours + 2, 1.2)


def candidate_conditions() -> tuple:
    """进入推荐流的候选集：正常、非广告、非置顶（与 list_posts 的推荐位口径一致）。"""
    return (
        Post.status == 1,
        Post.post_type != "advertisement",
        Post.is_pinned.is_(False),
    )


async def refresh_hot_scores(db: AsyncSession) -> int:
    """重算全部候选帖的热度分并落表，返回候选帖数。

    整个刷新在一个事务里完成：读接口要么看到上一轮榜单，要么看到新一轮，
    不会读到半更新的表。
    """
    conditions = candidate_conditions()
    candidate = select(
        Post.id.label("post_id"),
        hot_score_expr().label("score"),
    ).where(*conditions)

    insert = pg_insert(PostHotScore).from_select(["post_id", "score"], candidate)
    await db.execute(
        insert.on_conflict_do_update(
            index_elements=[PostHotScore.post_id],
            set_={"score": insert.excluded.score},
        )
    )
    # 清理不再合格的帖子（被隐藏、置顶或删除）
    await db.execute(
        delete(PostHotScore).where(
            ~select(Post.id)
            .where(Post.id == PostHotScore.post_id)
            .where(*conditions)
            .exists()
        )
    )
    count = int(
        (await db.execute(select(func.count()).select_from(candidate.subquery()))).scalar_one()
    )
    await db.execute(
        pg_insert(PostHotScoreState)
        .values(id=STATE_ROW_ID, computed_at=func.now(), post_count=count)
        .on_conflict_do_update(
            index_elements=[PostHotScoreState.id],
            set_={"computed_at": func.now(), "post_count": count},
        )
    )
    await db.commit()
    return count


async def hot_score_state(db: AsyncSession) -> PostHotScoreState | None:
    """读取榜单刷新状态（单行）。"""
    return (
        await db.execute(
            select(PostHotScoreState).where(PostHotScoreState.id == STATE_ROW_ID)
        )
    ).scalar_one_or_none()


async def hot_scores_usable(db: AsyncSession) -> bool:
    """榜单是否新鲜可用（worker 正常时每分钟刷新一次）。"""
    state = await hot_score_state(db)
    if state is None or state.computed_at is None:
        return False
    return state.computed_at >= datetime.now(timezone.utc) - timedelta(
        seconds=HOT_SCORE_STALE_SECONDS
    )
