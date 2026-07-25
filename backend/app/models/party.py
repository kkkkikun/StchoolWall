"""组局模型：组局/拼单帖 + 报名成员。"""
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(10), nullable=False)  # group(组局) / purchase(拼单)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    joined_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)  # 1招募中 2已满 -1已关闭
    meet_time = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PartyMember(Base):
    __tablename__ = "party_members"

    party_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("parties.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    joined_at = mapped_column(DateTime(timezone=True), server_default=func.now())
