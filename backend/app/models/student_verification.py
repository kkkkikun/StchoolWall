"""Student-card proofs are private; only keyed fingerprints leave the review workflow."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class StudentVerificationChallenge(Base):
    __tablename__ = "student_verification_challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(String(8))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentVerification(Base):
    __tablename__ = "student_verifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_verification_challenges.id"), unique=True
    )
    school_id: Mapped[str] = mapped_column(String(64))
    student_fingerprint: Mapped[str | None] = mapped_column(String(64))
    fingerprint_key_version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    consent_version: Mapped[str | None] = mapped_column(String(32))
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proof_key: Mapped[str | None] = mapped_column(String(255))
    card_valid_until: Mapped[date | None] = mapped_column(Date)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    review_reason: Mapped[str | None] = mapped_column(Text)
    verified_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    evidence_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index(
    "uq_student_verifications_pending_user",
    StudentVerification.user_id,
    unique=True,
    postgresql_where=text("status = 'pending'"),
)


class StudentIdentityClaim(Base):
    __tablename__ = "student_identity_claims"
    __table_args__ = (
        UniqueConstraint("school_id", "student_fingerprint", name="uq_student_claim_school_fingerprint"),
        UniqueConstraint("school_id", "user_id", name="uq_student_claim_school_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    school_id: Mapped[str] = mapped_column(String(64))
    student_fingerprint: Mapped[str] = mapped_column(String(64))
    fingerprint_key_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
