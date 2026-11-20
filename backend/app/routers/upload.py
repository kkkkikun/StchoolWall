from app.services.runtime_controls import require_publishing
"""Media upload and serving: private quarantine, opaque IDs, approved bytes only."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_posting_access
from app.services.runtime_controls import guest_posting_enabled
from app.models.media import MediaAsset
from app.models.user import User
from app.services.media import create_media, get_owned_media, media_bytes, media_url
from app.utils.rate_limit import RATE_UPLOAD, check_rate_limit
from app.utils.storage import MAX_FILE_SIZE, validate_file
import app.utils.storage as storage_module

router = APIRouter()
UPLOAD_KINDS = ("avatars", "banners", "posts", "parties")


@router.get("/config")
async def get_upload_config(
    filename: str = Query(..., min_length=1, max_length=255),
    content_type: str = Query("image/jpeg", max_length=100),
    user: User = Depends(require_posting_access),
):
    error = validate_file(filename, content_type)
    if error:
        raise HTTPException(status_code=400, detail=error)
    # Credentials for arbitrary object-store PUTs bypass quarantine verification.
    await check_rate_limit(f"rl:u:{user.id}:upload-config", *RATE_UPLOAD)
    return {"code": 0, "data": {"provider": "proxy", "method": "POST",
            "upload_url": "/api/v1/upload/direct", "form_data": {}, "public_url": None}}


@router.post("/direct", dependencies=[Depends(require_publishing)])
async def direct_upload(
    file: UploadFile,
    kind: str = Query(..., pattern="^(avatars|banners|posts|parties)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role not in {"student", "admin"} and (kind != "posts" or not await guest_posting_enabled()):
        raise HTTPException(403, "内测期间仅认证学生可上传内容图片")
    await check_rate_limit(f"rl:u:{user.id}:upload", *RATE_UPLOAD)
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    error = validate_file(file.filename, file.content_type or "")
    if error:
        raise HTTPException(status_code=400, detail=error)
    content = bytearray()
    while chunk := await file.read(256 * 1024):
        content.extend(chunk)
        if len(content) > storage_module.MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")
    try:
        asset = await create_media(db, user, kind, bytes(content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return {"code": 0, "data": {"media_id": str(asset.id), "status": asset.status, "public_url": None}}


@router.get("/media/{media_id}")
async def media_status(
    media_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    asset = await get_owned_media(db, media_id, user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    return {"code": 0, "data": {"media_id": str(asset.id), "status": asset.status,
            "public_url": media_url(asset) if asset.status == "approved" else None}}


@router.get("/media/{media_id}/content")
async def approved_media_content(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    asset = (await db.execute(select(MediaAsset).where(
        MediaAsset.id == media_id, MediaAsset.status == "approved",
    ))).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="图片不存在")
    try:
        content = await media_bytes(asset)
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="图片不存在") from None
    # Rejected or deleted content must disappear promptly, including browser copies.
    return Response(content=content, media_type=asset.content_type,
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
