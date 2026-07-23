"""互动模型：评论 / 点赞 / 收藏 / 浏览足迹。

计数不在此处聚合，而在写操作时同步维护 posts.like_count / comment_count，
列表页直接读冗余字段，避免 N 次聚合查询。
"""
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 1 正常 / -1 已删除（软删除，保留计数可追溯）
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Like(Base):
    __tablename__ = "likes"
    # 复合主键天然唯一，防重复点赞
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), primary_key=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), primary_key=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())


class Footprint(Base):
    """浏览足迹：用户查看帖子详情时记录一条。"""
    __tablename__ = "footprints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False)
    viewed_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
