import uuid

from sqlalchemy import Boolean, DateTime, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    openid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    student_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True, index=True)
    real_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    wechat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 我的主页横幅照片
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    bio: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 个人简介
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="guest")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
