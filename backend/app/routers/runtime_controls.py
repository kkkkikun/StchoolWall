from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.services.runtime_controls import PUBLISH_KEY, publishing_enabled
from app.services.admin_log import log_admin_action
from app.utils import redis as redis_module

router = APIRouter()
admin_router = APIRouter()

class Controls(BaseModel):
    publishing_enabled: bool

@router.get("/runtime-controls")
async def current():
    return {"code": 0, "data": {"publishing_enabled": await publishing_enabled()}}

@admin_router.put("/runtime-controls")
async def change(body: Controls, request: Request, actor: AdminActor = Depends(require_admin_console),
                 db: AsyncSession = Depends(get_db)):
    # Commit intent to audit first; a Redis failure is visible as 503 and can be retried.
    await log_admin_action(db, actor, "runtime.publishing", detail=body.model_dump(),
                           ip=request.client.host if request.client else None)
    await db.commit()
    await redis_module.redis_client.set(PUBLISH_KEY, "true" if body.publishing_enabled else "false")
    return {"code": 0, "data": {"publishing_enabled": await publishing_enabled()}}
