"""Appeals are private requests; accepting one never bypasses the publication state machine."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import AdminActor, get_current_user, require_admin_console
from app.models.appeal import Appeal
from app.models.post import Post
from app.models.interaction import Comment
from app.models.party import Party
from app.models.student_verification import StudentVerification
from app.models.user import User
from app.services.admin_log import log_admin_action
from app.utils.rate_limit import check_rate_limit

router = APIRouter()
admin_router = APIRouter()

class AppealCreate(BaseModel):
    entity_type: str = Field(pattern="^(post|comment|party|verification)$")
    entity_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=5, max_length=1000)

class AppealDecision(BaseModel):
    decision: str = Field(pattern="^(accepted|rejected)$")
    reason: str = Field(min_length=5, max_length=500)

def item(row):
    return {"id": str(row.id), "entity_type": row.entity_type, "entity_id": row.entity_id,
            "reason": row.reason, "status": row.status, "decision_reason": row.decision_reason,
            "created_at": row.created_at.isoformat()}

@router.post("")
async def create(body: AppealCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_rate_limit(f"rl:appeal:{user.id}", 5, 86400)
    model = {"post": Post, "comment": Comment, "party": Party, "verification": StudentVerification}[body.entity_type]
    try:
        key = uuid.UUID(body.entity_id) if body.entity_type == "verification" else int(body.entity_id)
    except ValueError:
        raise HTTPException(404, "申诉对象不存在") from None
    record = await db.get(model, key)
    if not record or record.user_id != user.id:
        raise HTTPException(404, "申诉对象不存在")
    if (body.entity_type != "verification" and record.status not in {0, -1}) or (
            body.entity_type == "verification" and record.status not in {"rejected", "revoked", "expired"}):
        raise HTTPException(409, "当前状态无需申诉")
    row = Appeal(user_id=user.id, entity_type=body.entity_type, entity_id=str(key), reason=body.reason)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "该内容已有待处理申诉") from None
    return {"code": 0, "data": item(row)}

@router.get("")
async def mine(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
               page: int = Query(1, ge=1)):
    rows = (await db.execute(select(Appeal).where(Appeal.user_id == user.id)
        .order_by(Appeal.created_at.desc(), Appeal.id).offset((page - 1) * 20).limit(20))).scalars()
    return {"code": 0, "data": {"items": [item(row) for row in rows]}}

@admin_router.get("")
async def listing(status: str = Query("pending", pattern="^(pending|accepted|rejected)$"),
                  page: int = Query(1, ge=1), db: AsyncSession = Depends(get_db),
                  actor: AdminActor = Depends(require_admin_console)):
    total = await db.scalar(select(func.count()).select_from(Appeal).where(Appeal.status == status))
    rows = (await db.execute(select(Appeal).where(Appeal.status == status)
        .order_by(Appeal.created_at, Appeal.id).offset((page - 1) * 20).limit(20))).scalars()
    return {"code": 0, "data": {"items": [item(row) for row in rows], "total": total}}

@admin_router.post("/{appeal_id}/decision")
async def decide(appeal_id: uuid.UUID, body: AppealDecision, request: Request,
                 db: AsyncSession = Depends(get_db), actor: AdminActor = Depends(require_admin_console)):
    row = await db.get(Appeal, appeal_id, with_for_update=True)
    if not row or row.status != "pending":
        raise HTTPException(409, "申诉状态已变化")
    row.status, row.decision_reason = body.decision, body.reason
    row.handled_at, row.handled_by = datetime.now(timezone.utc), actor.id
    await log_admin_action(db, actor, "appeal.decision", target_type="appeal", target_id=str(row.id),
                           detail={"decision": body.decision}, ip=request.client.host if request.client else None)
    await db.commit()
    return {"code": 0, "data": item(row), "message": "决定已记录；恢复内容仍需在对应审核页确认"}
