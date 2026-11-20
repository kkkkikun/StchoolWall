"""内部测试反馈；截图存于私有目录，不进公开媒体体系。"""
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 免登录提交（内部测试口令）时为空；登录用户不写真名/学号，只保留账号引用。
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    reporter_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    route: Mapped[str | None] = mapped_column(String(120), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    viewport: Mapped[str | None] = mapped_column(String(60), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(10), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # 客户端采集的诊断上下文（浏览器报错、失败请求、路由轨迹）。
    diagnostics = mapped_column(JSONB, nullable=True)
    # 私有截图清单：[{"name","path","size","content_type"}]
    screenshots = mapped_column(JSONB, nullable=True)
    # 截图上传令牌：免登录提交者据此继续上传截图，仅管理员可见列表不返回。
    upload_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    handled_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
