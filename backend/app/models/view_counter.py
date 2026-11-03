from sqlalchemy import BigInteger, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PostViewCounter(Base):
    """帖子浏览计数的异步聚合缓冲。

    热点帖详情页的浏览数不再同步写 posts 行：读路径只把增量写进本表，
    由 worker 周期性折叠回 posts.view_count。这样详情浏览与点赞/评论
    不再争同一行锁（见 docs/production/capacity.md 的瓶颈定位）。
    """

    __tablename__ = "post_view_counters"

    # 刻意不加外键：外键检查会对 posts 行取 KEY SHARE 锁，和热点帖的行锁互相冲突，
    # 会把刚拆掉的串行点重新引回来。本表只是计数缓冲，孤儿行无害（折叠时影响 0 行）。
    post_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
