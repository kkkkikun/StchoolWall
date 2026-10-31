import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class AdminUser(Base):
    """独立 Web 管理后台的账号（与小程序 users 表解耦）。

    - 密码只存 bcrypt 哈希，绝不存明文
    - pwd_version 用于改密后使所有已签发 token 失效
    - 无 role 列：当前只有一种管理员角色
    """

    __tablename__ = "admin_users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 改密 +1；token 中的 pwd_version 与库不匹配即失效
    pwd_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_last_counter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_login_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
