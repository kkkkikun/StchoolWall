from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AdminLog(Base):
    """管理员操作审计日志。

    admin_id 存字符串不加 FK：console（admin_users）与 legacy（users）双体系统一留痕。
    admin_name 是操作时的昵称快照（防账号改名/删除后不可读）。
    """

    __tablename__ = "admin_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    admin_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # "console" | "legacy"
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # "post" | "user" | "report" | "banner" | "comment" | "party" | "announcement" | ...
    target_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detail = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


Index(
    "ix_admin_logs_admin_time",
    AdminLog.__table__.c.admin_id,
    AdminLog.__table__.c.created_at.desc(),
)
