import uuid
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base

class Appeal(Base):
    __tablename__ = "appeals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    handled_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())

Index("uq_appeals_pending_entity", Appeal.user_id, Appeal.entity_type, Appeal.entity_id,
      unique=True, postgresql_where=text("status = 'pending'"))
