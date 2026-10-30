"""Explicit human decisions for durable moderation jobs, with audited previews."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.models.job import Job
from app.models.media import MediaAsset
from app.models.post import Post
from app.models.interaction import Comment
from app.models.party import Party
from app.services.admin_log import log_admin_action
from app.services.media import entity_media, media_bytes, media_url, publish_entity_media, reject_entity_media
from app.services.moderation import apply_profile_update

router = APIRouter()
REVIEWABLE = {"review", "dead", "pending", "rejected"}

class Decision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    reason: str = Field(min_length=2, max_length=300)

async def _preview(db, job):
    payload = job.payload
    media_ids = []
    text = ""
    status = None
    if job.kind == "moderate_profile":
        text = "\n".join(str(payload.get("updates", {}).get(key) or "") for key in ("nickname", "bio", "wechat_id"))
        media_ids = list(payload.get("media", {}).values())
    elif job.kind == "moderate_media":
        media_ids = [payload["media_id"]]
    elif job.kind == "moderate_post":
        post = await db.get(Post, int(payload["post_id"]))
        if post:
            text, status = post.content, post.status
            media_ids = [str(a.id) for a in await entity_media(db, "post", post.id)]
    elif job.kind == "moderate_comment":
        item = await db.get(Comment, int(payload["comment_id"]))
        if item:
            text, status = item.content, item.status
    elif job.kind == "moderate_party":
        item = await db.get(Party, int(payload["party_id"]))
        if item:
            text, status = "\n".join([item.title or "", item.content or "", item.location or ""]), item.status
    return {"id": str(job.id), "kind": job.kind, "status": job.status, "attempts": job.attempts,
            "last_error": job.last_error, "created_at": job.created_at.isoformat(),
            "text": text, "entity_status": status, "media_ids": media_ids}

@router.get("")
async def list_jobs(status: str = Query("review", pattern="^(review|dead|pending|rejected|succeeded)$"),
                    page: int = Query(1, ge=1), db: AsyncSession = Depends(get_db),
                    actor: AdminActor = Depends(require_admin_console)):
    total = await db.scalar(select(func.count()).select_from(Job).where(Job.status == status))
    rows = (await db.execute(select(Job).where(Job.status == status)
        .order_by(Job.created_at, Job.id).offset((page - 1) * 20).limit(20))).scalars()
    return {"code": 0, "data": {"items": [await _preview(db, job) for job in rows], "total": total}}

@router.get("/{job_id}/media/{media_id}")
async def preview_media(job_id: uuid.UUID, media_id: uuid.UUID, request: Request,
                        db: AsyncSession = Depends(get_db), actor: AdminActor = Depends(require_admin_console)):
    job = await db.get(Job, job_id)
    if not job or str(media_id) not in (await _preview(db, job))["media_ids"]:
        raise HTTPException(404, "图片不存在")
    asset = await db.get(MediaAsset, media_id)
    if not asset or asset.status == "deleted":
        raise HTTPException(404, "图片不存在")
    try:
        content = await media_bytes(asset)
    except (OSError, ValueError):
        raise HTTPException(404, "图片不存在") from None
    await log_admin_action(db, actor, "moderation.media_view", target_type="media",
                           target_id=str(media_id), ip=request.client.host if request.client else None)
    await db.commit()
    return Response(content, media_type=asset.content_type, headers={"Cache-Control": "no-store"})

@router.post("/{job_id}/retry")
async def retry_job(job_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db),
                    actor: AdminActor = Depends(require_admin_console)):
    job = await db.get(Job, job_id, with_for_update=True)
    if not job or job.status not in {"review", "dead"}:
        raise HTTPException(409, "任务当前不可重试")
    job.status, job.attempts, job.last_error = "pending", 0, None
    job.available_at = datetime.now(timezone.utc)
    job.lease_token = job.lease_until = None
    await log_admin_action(db, actor, "moderation.retry", target_type="job", target_id=str(job.id),
                           ip=request.client.host if request.client else None)
    await db.commit()
    return {"code": 0}

@router.post("/{job_id}/review")
async def review_job(job_id: uuid.UUID, body: Decision, request: Request,
                     db: AsyncSession = Depends(get_db), actor: AdminActor = Depends(require_admin_console)):
    job = await db.get(Job, job_id, with_for_update=True)
    if not job or job.status not in REVIEWABLE:
        raise HTTPException(409, "任务当前不可审核，请刷新")
    approved = body.decision == "approve"
    if job.kind == "moderate_post":
        from app.services.admin import admin_update_post_status
        item = await db.get(Post, int(job.payload["post_id"]), with_for_update=True)
        if not item or item.status != 0:
            raise HTTPException(409, "帖子已有新决定")
        await admin_update_post_status(db, item.id, 1 if approved else -1)
    elif job.kind == "moderate_comment":
        from app.services.admin_comment import admin_update_comment_status
        item = await db.get(Comment, int(job.payload["comment_id"]), with_for_update=True)
        if not item or item.status != 0:
            raise HTTPException(409, "评论已有新决定")
        _, error = await admin_update_comment_status(db, item.id, 1 if approved else -1)
        if error:
            raise HTTPException(409, error)
    elif job.kind == "moderate_party":
        from app.services.admin_party import admin_update_party_status
        item = await db.get(Party, int(job.payload["party_id"]), with_for_update=True)
        if not item or item.status != 0:
            raise HTTPException(409, "组局已有新决定")
        await admin_update_party_status(db, item.id, 1 if approved else -1)
    elif job.kind == "moderate_media":
        asset = await db.get(MediaAsset, uuid.UUID(job.payload["media_id"]), with_for_update=True)
        if not asset or asset.status != "quarantine":
            raise HTTPException(409, "图片已有新决定")
        asset.status = "approved" if approved else "rejected"
        asset.public_path = media_url(asset) if approved else None
    elif job.kind == "moderate_profile":
        if approved and not await apply_profile_update(db, job.payload):
            raise HTTPException(409, "资料已有新版本，请审核最新申请")
    else:
        raise HTTPException(400, "不支持的审核类型")
    job.status = "succeeded" if approved else "rejected"
    job.lease_token = job.lease_until = None
    job.last_error = None
    await log_admin_action(db, actor, "moderation.review", target_type="job", target_id=str(job.id),
                           detail={"decision": body.decision, "reason": body.reason},
                           ip=request.client.host if request.client else None)
    await db.commit()
    return {"code": 0, "data": {"status": job.status}}
