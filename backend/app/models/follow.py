"""用户关注关系模型。"""
import uuid

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class UserFollow(Base):
    __tablename__ = "user_follows"
    __table_args__ = (Index("ix_user_follows_followee", "followee_id"),)

    follower_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    followee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
