import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, get_current_user, require_admin_console
from app.models.user import User
from app.schemas.student_verification import VerificationReview, VerificationRevoke
from app.services import student_verification as service
from app.utils.rate_limit import check_rate_limit

router = APIRouter()
admin_router = APIRouter()


@router.post("/challenge")
async def create_challenge(request: Request, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)):
    await check_rate_limit(f"rl:verification:challenge:{user.id}", 5, 3600)
    return {"code": 0, "data": await service.create_challenge(db, user)}


@router.get("/me")
async def current_verification(user: User = Depends(get_current_user),
                               db: AsyncSession = Depends(get_db)):
    return {"code": 0, "data": await service.current_verification(db, user)}


@router.post("")
async def submit(
    verification_id: uuid.UUID = Form(...), challenge_code: str = Form(..., max_length=8),
    student_id: str = Form(..., min_length=4, max_length=32),
    consent_version: str = Form(..., max_length=32),
    card_valid_until: date | None = Form(None), file: UploadFile = File(...),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    await check_rate_limit(f"rl:verification:submit:{user.id}", 5, 3600)
    data = await service.submit_verification(
        db, user, verification_id, challenge_code, student_id, card_valid_until, file, consent_version
    )
    return {"code": 0, "data": data}


@admin_router.get("")
async def list_records(
    status: str | None = Query("pending", pattern="^(draft|pending|approved|rejected|expired|revoked)$"),
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    actor: AdminActor = Depends(require_admin_console), db: AsyncSession = Depends(get_db),
):
    return {"code": 0, "data": await service.list_verifications(db, status, page, page_size)}


@admin_router.get("/{record_id}/evidence")
async def evidence(record_id: uuid.UUID, request: Request,
                   actor: AdminActor = Depends(require_admin_console),
                   db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    content = await service.get_evidence(db, record_id, actor, ip)
    return Response(content=content, media_type="image/jpeg", headers={
        "Cache-Control": "no-store, private", "Pragma": "no-cache",
        "Content-Disposition": 'inline; filename="student-verification.jpg"',
    })


@admin_router.post("/{record_id}/review")
async def review(record_id: uuid.UUID, body: VerificationReview, request: Request,
                 actor: AdminActor = Depends(require_admin_console),
                 db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    return {"code": 0, "data": await service.review_verification(db, record_id, body, actor, ip)}


@admin_router.post("/{record_id}/revoke")
async def revoke(record_id: uuid.UUID, body: VerificationRevoke, request: Request,
                 actor: AdminActor = Depends(require_admin_console),
                 db: AsyncSession = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    return {"code": 0, "data": await service.revoke_verification(db, record_id, body.reason, actor, ip)}
