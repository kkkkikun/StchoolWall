import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    post_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    images = mapped_column(JSONB, default=[])
    price = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=0, index=True)
    # 管理员置顶：仅首页"推荐"位第一页前置展示
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pinned_at = mapped_column(DateTime(timezone=True), nullable=True)
    # 精华：经验贴等长尾价值内容，进"精华"流（历史热度排序，无时间衰减）
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    featured_at = mapped_column(DateTime(timezone=True), nullable=True)
    # 互动计数（冗余字段，写操作时同步维护，列表页避免聚合查询）
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
