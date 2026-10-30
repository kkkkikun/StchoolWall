"""Manual student-card verification; academic-system credentials are never collected."""
import hashlib
import hmac
import json
import re
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import AdminActor
from app.models.student_verification import (
    StudentIdentityClaim, StudentVerification, StudentVerificationChallenge,
)
from app.models.user import User
from app.schemas.student_verification import VerificationReview
from app.services.admin_log import log_admin_action
from app.utils.verification_storage import VerificationStorage, read_proof

CHALLENGE_LIFETIME = timedelta(minutes=10)
PENDING_LIFETIME = timedelta(days=14)
RESULT_EVIDENCE_LIFETIME = timedelta(days=7)
GENERIC_CONFLICT = "资料暂时无法完成认证，请检查资料或联系支持"
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_student_id(value: str) -> str:
    value = re.sub(r"\s+", "", value).upper()
    if not re.fullmatch(r"[A-Z0-9-]{4,32}", value):
        raise HTTPException(400, "请输入有效学号（4–32 位字母、数字或连字符）")
    return value


def fingerprint(student_id: str, school_id: str, key: str) -> str:
    return hmac.new(
        key.encode(), f"{school_id}\0{normalize_student_id(student_id)}".encode(),
        hashlib.sha256,
    ).hexdigest()


def fingerprint_keys() -> dict[str, str]:
    try:
        keys = json.loads(settings.VERIFICATION_FINGERPRINT_PREVIOUS_KEYS or "{}")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("认证指纹历史密钥配置无效") from exc
    if not isinstance(keys, dict):
        raise RuntimeError("认证指纹历史密钥配置无效")
    keys[settings.VERIFICATION_FINGERPRINT_KEY_VERSION] = settings.VERIFICATION_FINGERPRINT_KEY
    if not all(isinstance(k, str) and isinstance(v, str) and len(v) >= 32 for k, v in keys.items()):
        raise RuntimeError("认证指纹密钥必须独立配置，至少 32 字符")
    return keys


def ensure_enabled() -> None:
    if not settings.STUDENT_VERIFICATION_ENABLED:
        raise HTTPException(503, "学生证认证暂未开放")
    fingerprint_keys()


def public_record(row: StudentVerification | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.id), "school_id": row.school_id, "status": row.status,
        "created_at": row.created_at, "submitted_at": row.submitted_at,
        "reviewed_at": row.reviewed_at, "review_reason": row.review_reason,
        "verified_until": row.verified_until, "evidence_delete_after": row.evidence_delete_after,
    }


async def create_challenge(db: AsyncSession, user: User) -> dict:
    ensure_enabled()
    await db.execute(select(User).where(User.id == user.id).with_for_update())
    pending = await db.scalar(select(StudentVerification.id).where(
        StudentVerification.user_id == user.id, StudentVerification.status == "pending"
    ))
    if pending:
        raise HTTPException(409, "已有申请正在审核")
    drafts = (await db.scalars(select(StudentVerification).where(
        StudentVerification.user_id == user.id, StudentVerification.status == "draft"
    ))).all()
    for draft in drafts:
        draft.status = "expired"
    challenge = StudentVerificationChallenge(
        user_id=user.id, code="".join(secrets.choice(CODE_ALPHABET) for _ in range(6)),
        expires_at=utcnow() + CHALLENGE_LIFETIME,
    )
    db.add(challenge)
    await db.flush()
    record = StudentVerification(user_id=user.id, challenge_id=challenge.id,
                                 school_id=settings.VERIFICATION_SCHOOL_ID, status="draft")
    db.add(record)
    await db.commit()
    return {
        "verification_id": str(record.id), "challenge_id": str(challenge.id),
        "code": challenge.code, "expires_at": challenge.expires_at,
        "school_id": record.school_id, "school_name": settings.VERIFICATION_SCHOOL_NAME,
    }


async def current_verification(db: AsyncSession, user: User) -> dict:
    row = await db.scalar(select(StudentVerification).where(
        StudentVerification.user_id == user.id
    ).order_by(StudentVerification.created_at.desc()).limit(1))
    result = public_record(row)
    if row and row.status == "pending" and row.submitted_at + PENDING_LIFETIME <= utcnow():
        result["status"] = "expired"
    if row and row.status == "approved" and row.verified_until <= utcnow():
        result["status"] = "expired"
    return {"enabled": settings.STUDENT_VERIFICATION_ENABLED,
            "school_name": settings.VERIFICATION_SCHOOL_NAME, "verification": result}


async def _check_existing_claim(
    db: AsyncSession, user: User, school_id: str, student_id: str
) -> None:
    candidates = [fingerprint(student_id, school_id, key) for key in fingerprint_keys().values()]
    claims = (await db.scalars(select(StudentIdentityClaim).where(
        StudentIdentityClaim.school_id == school_id,
        or_(StudentIdentityClaim.student_fingerprint.in_(candidates),
            StudentIdentityClaim.user_id == user.id),
    ))).all()
    if any(claim.user_id != user.id or claim.student_fingerprint not in candidates for claim in claims):
        raise HTTPException(409, GENERIC_CONFLICT)


async def submit_verification(
    db: AsyncSession, user: User, verification_id: uuid.UUID, challenge_code: str,
    student_id: str, card_valid_until: date | None, file: UploadFile, consent_version: str,
) -> dict:
    ensure_enabled()
    if consent_version != 'student-card-v1':
        raise HTTPException(400, '请阅读并单独同意学生证认证隐私说明')
    await db.execute(select(User).where(User.id == user.id).with_for_update())
    row = await db.scalar(select(StudentVerification).where(
        StudentVerification.id == verification_id, StudentVerification.user_id == user.id
    ).with_for_update())
    if row is None:
        raise HTTPException(404, "认证申请不存在")
    challenge = await db.scalar(select(StudentVerificationChallenge).where(
        StudentVerificationChallenge.id == row.challenge_id
    ).with_for_update())
    if row.status != "draft" or challenge.consumed_at or challenge.expires_at <= utcnow():
        raise HTTPException(409, "拍摄码已失效，请重新获取")
    if not hmac.compare_digest(challenge.code, challenge_code.strip().upper()):
        raise HTTPException(400, "拍摄码不正确")
    if card_valid_until and card_valid_until < utcnow().date():
        raise HTTPException(400, "学生证已超过有效期")
    normalized = normalize_student_id(student_id)
    await _check_existing_claim(db, user, row.school_id, normalized)
    content = await read_proof(file)
    storage = VerificationStorage()
    key = f"evidence/{row.id}/{uuid.uuid4().hex}.jpg"
    await storage.save(key, content)
    try:
        now = utcnow()
        challenge.consumed_at = now
        row.status = "pending"
        row.student_fingerprint = fingerprint(
            normalized, row.school_id, settings.VERIFICATION_FINGERPRINT_KEY
        )
        row.fingerprint_key_version = settings.VERIFICATION_FINGERPRINT_KEY_VERSION
        row.proof_key = key
        row.consent_version, row.consented_at = consent_version, now
        row.card_valid_until = card_valid_until
        row.submitted_at = now
        row.evidence_delete_after = now + PENDING_LIFETIME
        await db.commit()
    except Exception:
        await db.rollback()
        await storage.delete(key)
        raise
    return public_record(row)


async def list_verifications(db: AsyncSession, status: str | None, page: int, page_size: int) -> dict:
    conditions = [StudentVerification.status == status] if status else []
    total = await db.scalar(select(func.count()).select_from(StudentVerification).where(*conditions))
    records = (await db.execute(select(StudentVerification, User.nickname,
        StudentVerificationChallenge.code).join(User, User.id == StudentVerification.user_id)
        .join(StudentVerificationChallenge,
              StudentVerificationChallenge.id == StudentVerification.challenge_id)
        .where(*conditions).order_by(StudentVerification.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size))).all()
    return {"items": [{**public_record(row), "user_id": str(row.user_id), "nickname": nickname,
                       "challenge_code": code, "card_valid_until": row.card_valid_until,
                       "evidence_available": bool(row.proof_key and
                            row.evidence_delete_after and row.evidence_delete_after > utcnow())}
                      for row, nickname, code in records],
            "total": total or 0, "page": page, "page_size": page_size}


async def get_evidence(db: AsyncSession, record_id: uuid.UUID, actor: AdminActor, ip: str) -> bytes:
    row = await db.get(StudentVerification, record_id)
    if not row or not row.proof_key or not row.evidence_delete_after or row.evidence_delete_after <= utcnow():
        raise HTTPException(404, "认证照片不存在或已按保留期限删除")
    await log_admin_action(db, actor, "verification.evidence_view",
                           target_type="verification", target_id=row.id, ip=ip)
    await db.commit()
    return await VerificationStorage().read(row.proof_key)


async def review_verification(
    db: AsyncSession, record_id: uuid.UUID, body: VerificationReview,
    actor: AdminActor, ip: str,
) -> dict:
    row = await db.scalar(select(StudentVerification).where(
        StudentVerification.id == record_id).with_for_update())
    if row is None:
        raise HTTPException(404, "认证申请不存在")
    if row.status != "pending" or row.submitted_at + PENDING_LIFETIME <= utcnow():
        raise HTTPException(409, "申请状态已变化，请刷新")
    user = await db.scalar(select(User).where(User.id == row.user_id).with_for_update())
    now = utcnow()
    if body.decision == "approved":
        try:
            await _approve(db, row, user, body, now)
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(409, GENERIC_CONFLICT) from exc
    elif not body.reason.strip():
        raise HTTPException(400, "请填写不含个人敏感信息的拒绝原因")
    row.status = body.decision
    row.reviewed_at, row.reviewed_by = now, actor.id
    row.review_reason = body.reason.strip() or None
    row.evidence_delete_after = now + RESULT_EVIDENCE_LIFETIME
    await log_admin_action(db, actor, "verification.review", target_type="verification",
                           target_id=row.id, detail={"decision": body.decision}, ip=ip)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, GENERIC_CONFLICT) from exc
    return public_record(row)


async def _approve(
    db: AsyncSession, row: StudentVerification, user: User,
    body: VerificationReview, now: datetime,
) -> None:
    if not (body.challenge_matches and body.school_matches and body.student_number_matches and body.validity_checked):
        raise HTTPException(400, "请逐项核对学生证与同框拍摄码")
    keys = fingerprint_keys()
    key = keys.get(row.fingerprint_key_version)
    if not key or not body.student_id:
        raise HTTPException(400, "请录入照片上可见的学号供系统核对")
    actual = fingerprint(body.student_id, row.school_id, key)
    if not hmac.compare_digest(actual, row.student_fingerprint):
        raise HTTPException(400, "照片学号与申请不符")
    await _check_existing_claim(db, user, row.school_id, body.student_id)
    card_date = body.card_valid_until or row.card_valid_until
    if card_date and card_date < now.date():
        raise HTTPException(400, "学生证已过期")
    try:
        valid_until = now.replace(year=now.year + 1)
    except ValueError:
        valid_until = now.replace(year=now.year + 1, day=28)
    if card_date:
        valid_until = min(valid_until, datetime.combine(card_date + timedelta(days=1),
                                                       time.min, tzinfo=ZoneInfo('Asia/Shanghai')).astimezone(timezone.utc))
    claim = await db.scalar(select(StudentIdentityClaim).where(
        StudentIdentityClaim.user_id == user.id, StudentIdentityClaim.school_id == row.school_id
    ).with_for_update())
    if not claim:
        db.add(StudentIdentityClaim(
            user_id=user.id, school_id=row.school_id,
            student_fingerprint=row.student_fingerprint,
            fingerprint_key_version=row.fingerprint_key_version,
        ))
    previous = (await db.scalars(select(StudentVerification).where(
        StudentVerification.user_id == user.id,
        StudentVerification.status == 'approved', StudentVerification.id != row.id,
    ))).all()
    for prior in previous:
        prior.status, prior.review_reason = 'revoked', '认证已更新'
    row.card_valid_until, row.verified_until = card_date, valid_until
    user.is_verified, user.verified_until = True, valid_until
    if user.role != "admin":
        user.role = "student"


async def revoke_verification(
    db: AsyncSession, record_id: uuid.UUID, reason: str, actor: AdminActor, ip: str
) -> dict:
    row = await db.scalar(select(StudentVerification).where(
        StudentVerification.id == record_id).with_for_update())
    if not row or row.status != "approved":
        raise HTTPException(409, "只有已通过的申请可以撤销")
    user = await db.scalar(select(User).where(User.id == row.user_id).with_for_update())
    row.status, row.review_reason = "revoked", reason.strip()
    user.is_verified, user.verified_until = False, None
    if user.role == "student":
        user.role = "guest"
    row.evidence_delete_after = min(row.evidence_delete_after, utcnow() + RESULT_EVIDENCE_LIFETIME)
    await log_admin_action(db, actor, "verification.revoke", target_type="verification",
                           target_id=row.id, ip=ip)
    await db.commit()
    return public_record(row)


async def cleanup_expired_verifications(db: AsyncSession, limit: int = 200) -> dict:
    now = utcnow()
    expiring = (await db.scalars(select(StudentVerification).where(or_(
        (StudentVerification.status == "pending") &
        (StudentVerification.submitted_at <= now - PENDING_LIFETIME),
        (StudentVerification.status == "approved") & (StudentVerification.verified_until <= now),
        (StudentVerification.status == "draft") & (StudentVerification.created_at <= now - CHALLENGE_LIFETIME),
    )).with_for_update(skip_locked=True).limit(limit))).all()
    for row in expiring:
        was_approved = row.status == "approved"
        row.status = "expired"
        if not was_approved:
            row.evidence_delete_after = now
        if was_approved:
            user = await db.get(User, row.user_id)
            if user and user.verified_until and user.verified_until <= now:
                user.is_verified, user.verified_until = False, None
                if user.role == "student":
                    user.role = "guest"
    await db.commit()
    removable = (await db.scalars(select(StudentVerification).where(
        StudentVerification.proof_key.is_not(None),
        StudentVerification.evidence_delete_after <= now,
    ).with_for_update(skip_locked=True).limit(limit))).all()
    storage = VerificationStorage() if (removable or settings.STUDENT_VERIFICATION_ENABLED) else None
    for row in removable:
        await storage.delete(row.proof_key)
        row.proof_key, row.evidence_deleted_at = None, now
    await db.commit()
    orphan_count = 0
    if storage:
        active_keys = set((await db.scalars(select(StudentVerification.proof_key).where(
            StudentVerification.proof_key.is_not(None)))).all())
        orphan_count = await storage.cleanup_orphans(active_keys, now - PENDING_LIFETIME, limit)
    return {"expired": len(expiring), "evidence_deleted": len(removable), "orphans_deleted": orphan_count}
