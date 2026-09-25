from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Banner(Base):
    """首页轮播广告位（运营位，与帖子内容解耦）

    跳转目标二选一：post_id（站内帖子详情）或 link_url（外部链接）。
    投放窗口：start_at/end_at 为空分别表示立即开始/永久有效。
    """

    __tablename__ = "banners"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    desc: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # 有图用图片 banner，无图走 emoji+渐变文案样式
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    post_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=True)
    # 站内活动页跳转（与 post_id / link_url 三选一；不建外键，删除活动时前端兜底 404）
    activity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # 排序权重，越大越靠前
    sort: Mapped[int] = mapped_column(Integer, default=0)
    # 1=投放中 0=已下架
    status: Mapped[int] = mapped_column(SmallInteger, default=1, index=True)
    start_at = mapped_column(DateTime(timezone=True), nullable=True)
    end_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
