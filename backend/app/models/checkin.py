"""签到模型：每日一行，(user_id, check_date) 唯一防重复。

收益体系（积分/奖励）产品尚未定稿，先落机制：日期、连签由查询推导，
不存易漂移的冗余字段——收益规则确定后在此表加列即可，历史签到不丢。
"""
import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CheckIn(Base):
    __tablename__ = "check_ins"
    # 同一天二次签到直接被唯一约束挡住（应用层也会先查，双保险）
    __table_args__ = (
        UniqueConstraint("user_id", "check_date", name="uq_checkin_user_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # 自然日按 Asia/Shanghai 切（校园场景全员同一时区）
    check_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

