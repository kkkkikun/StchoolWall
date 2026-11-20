from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PostHotScore(Base):
    """推荐流热度分的预计算榜单。

    热度分含 `now()`，PostgreSQL 无法用表达式索引直接排序，推荐流只能全表扫描
    后再 Sort（docs/production/capacity.md 实测单次 662.276ms）。本表由 worker
    按固定周期把热度分算好落库，查询只做 `(score, post_id)` 索引扫描 + 键集分页。

    刻意不加到 posts.id 的外键：本表只是榜单副本，外键检查会对 posts 行取
    KEY SHARE 锁，与帖子互动路径的行锁冲突（同 post_view_counters 的取舍）。
    """

    __tablename__ = "post_hot_scores"
    __table_args__ = (
        # 榜单排序 + 键集分页：(score, id) 复合索引，倒序扫描即推荐流顺序
        Index("ix_post_hot_scores_rank", "score", "post_id"),
    )

    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)


class PostHotScoreState(Base):
    """预计算榜单的刷新状态（单行，id=1）。

    读接口据此判断榜单是否新鲜：worker 正常时每分钟刷新一次，榜单过期则退回
    实时计算（降级路径，保证结果始终正确）。
    """

    __tablename__ = "post_hot_score_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
