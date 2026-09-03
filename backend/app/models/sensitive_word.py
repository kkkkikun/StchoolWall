from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SensitiveWord(Base):
    """敏感词库（管理后台维护，审核时全量读取）。

    level: "hard" 命中直接拒绝；"gray" 命中转人工。
    created_by 存字符串不加 FK，同 AdminLog.admin_id 双体系约定。
    """

    __tablename__ = "sensitive_words"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    word: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # "hard" | "gray"
    level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
