from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_owner
from app.services.admin_log import log_admin_action
from app.services.runtime_controls import get_runtime_controls, update_runtime_controls

router = APIRouter()
admin_router = APIRouter()


class Controls(BaseModel):
    publishing_enabled: bool | None = None
    moderation_enabled: bool | None = None
    sensitive_words_enabled: bool | None = None
    registration_enabled: bool | None = None
    guest_posting_enabled: bool | None = None
    guest_interaction_enabled: bool | None = None


@router.get("/runtime-controls")
async def current():
    return {"code": 0, "data": await get_runtime_controls()}


@admin_router.get("/runtime-controls")
async def admin_current(actor: AdminActor = Depends(require_admin_owner)):
    return {"code": 0, "data": await get_runtime_controls()}


@admin_router.put("/runtime-controls")
async def change(body: Controls, request: Request, actor: AdminActor = Depends(require_admin_owner),
                 db: AsyncSession = Depends(get_db)):
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(400, "没有可更新的设置")
    action = "runtime.publishing" if set(changes) == {"publishing_enabled"} else "runtime.controls"
    # Audit the intent before Redis; a failure is visible as 503 and can be retried.
    await log_admin_action(db, actor, action, detail=changes,
                           ip=request.client.host if request.client else None)
    await db.commit()
    await update_runtime_controls(changes)
    return {"code": 0, "data": await get_runtime_controls()}
