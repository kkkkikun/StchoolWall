from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ModerationRecord(Base):
    """机器审核记录：每次帖子审核按来源（rule/wechat）各落一行，可追溯可调参。"""

    __tablename__ = "moderation_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), nullable=False, index=True)
    # 评论审核记录（帖审核为空）；评论被硬词直接拒时 comment_id 为空、post_id 指向被评帖
    comment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("comments.id"), nullable=True, index=True)
    # "rule"（本地敏感词/频率） | "wechat"（msgSecCheck/imgSecCheck）
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # "pass" | "review" | "reject" | "error"
    verdict: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # 命中的（归一化）敏感词列表，仅 rule 来源使用
    matched = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
