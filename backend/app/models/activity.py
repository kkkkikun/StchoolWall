"""站内活动/专题页模型：轮播可挂载到自有 H5 二级页，避免外链跳转。"""
from sqlalchemy import BigInteger, DateTime, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_at = mapped_column(DateTime(timezone=True), nullable=True)
    end_at = mapped_column(DateTime(timezone=True), nullable=True)
    # 1=上架 0=下架
    status: Mapped[int] = mapped_column(SmallInteger, default=1, index=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
