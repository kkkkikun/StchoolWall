"""Ownership, quarantine and image normalization for user supplied media."""
import asyncio
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.media import MediaAsset
from app.models.user import User
from app.services.jobs import enqueue_job
from app.utils.storage import MAX_FILE_SIZE, read_private_media, write_private_media, delete_private_media, old_private_media_keys

MEDIA_PURPOSES = {"avatars", "banners", "posts", "parties"}
_IMAGE_DECODE_LIMIT = asyncio.Semaphore(1)


def normalize_image(content: bytes) -> bytes:
    """Decode real pixels and re-encode a metadata-free, non-animated JPEG."""
    if not content or len(content) > MAX_FILE_SIZE:
        raise ValueError("图片为空或超过 10MB 限制")
    try:
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            max_pixels = getattr(settings, "MEDIA_MAX_PIXELS", 25_000_000)
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise ValueError("图片像素尺寸超过限制")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("暂不支持动态图片")
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            clean = Image.frombytes("RGB", image.size, image.tobytes())
            output = io.BytesIO()
            clean.save(output, format="JPEG", quality=85, optimize=True)
            result = output.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("无法解码有效图片") from exc
    if len(result) > MAX_FILE_SIZE:
        raise ValueError("图片转换后超过大小限制")
    return result


async def create_media(db: AsyncSession, user: User, purpose: str, content: bytes) -> MediaAsset:
    if purpose not in MEDIA_PURPOSES:
        raise ValueError("非法上传用途")
    async with _IMAGE_DECODE_LIMIT:
        normalized = await asyncio.to_thread(normalize_image, content)
    media_id = uuid.uuid4()
    key = f"quarantine/{media_id.hex}.jpg"
    await write_private_media(key, normalized)
    asset = MediaAsset(id=media_id, owner_id=user.id, purpose=purpose, storage_key=key,
                       content_type="image/jpeg", size_bytes=len(normalized),
                       sha256=hashlib.sha256(normalized).hexdigest(), status="quarantine")
    db.add(asset)
    await db.flush()
    await enqueue_job(db, "moderate_media", {"media_id": str(media_id)}, f"media:{media_id}")
    # The caller commits asset + outbox together; a rollback leaves only an unreferenced
    # private object, removed by the regular orphan cleanup.
    return asset


def media_url(asset: MediaAsset) -> str:
    return f"/api/v1/upload/media/{asset.id}/content"


async def get_owned_media(db: AsyncSession, media_id: uuid.UUID, owner_id: uuid.UUID) -> MediaAsset | None:
    return (await db.execute(select(MediaAsset).where(
        MediaAsset.id == media_id, MediaAsset.owner_id == owner_id,
    ))).scalar_one_or_none()


async def bind_media(db: AsyncSession, owner_id: uuid.UUID, ids: list[uuid.UUID],
                     purpose: str, entity_type: str, entity_id: int) -> list[MediaAsset]:
    if len(ids) != len(set(ids)):
        raise ValueError("图片不可重复")
    if not ids:
        return []
    rows = list((await db.execute(select(MediaAsset).where(
        MediaAsset.id.in_(ids), MediaAsset.owner_id == owner_id, MediaAsset.purpose == purpose,
    ).with_for_update())).scalars())
    if len(rows) != len(ids):
        raise ValueError("图片不存在、用途不符或不属于当前账号")
    for asset in rows:
        if asset.status in {"rejected", "deleted"}:
            raise ValueError("图片已被拒绝或已删除")
        if asset.entity_type and (asset.entity_type != entity_type or asset.entity_id != entity_id):
            raise ValueError("图片已用于其他内容")
        asset.entity_type, asset.entity_id = entity_type, entity_id
    return rows


async def entity_media(db: AsyncSession, entity_type: str, entity_id: int) -> list[MediaAsset]:
    return list((await db.execute(select(MediaAsset).where(
        MediaAsset.entity_type == entity_type, MediaAsset.entity_id == entity_id,
    ).order_by(MediaAsset.created_at, MediaAsset.id))).scalars())


async def publish_entity_media(db: AsyncSession, entity_type: str, entity_id: int) -> list[str]:
    rows = await entity_media(db, entity_type, entity_id)
    for asset in rows:
        if asset.status in {"rejected", "deleted"}:
            raise ValueError("内容含已拒绝图片，请移除后重新提交")
        asset.status = "approved"
        asset.public_path = media_url(asset)
    return [media_url(asset) for asset in rows]


async def reject_entity_media(db: AsyncSession, entity_type: str, entity_id: int) -> None:
    for asset in await entity_media(db, entity_type, entity_id):
        asset.status, asset.public_path = "rejected", None


async def media_bytes(asset: MediaAsset) -> bytes:
    return await read_private_media(asset.storage_key)


async def cleanup_unbound_media(db: AsyncSession) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    rows = list((await db.execute(select(MediaAsset).where(
        MediaAsset.entity_type.is_(None), MediaAsset.created_at < cutoff,
        MediaAsset.status != "deleted",
    ).with_for_update(skip_locked=True).limit(100))).scalars())
    for asset in rows:
        await delete_private_media(asset.storage_key)
        asset.status, asset.public_path = "deleted", None
    await db.commit()
    candidates = await old_private_media_keys(cutoff)
    if candidates:
        known = set((await db.execute(select(MediaAsset.storage_key).where(
            MediaAsset.storage_key.in_(candidates),
        ))).scalars())
        for key in candidates:
            if key not in known:
                await delete_private_media(key)
    return len(rows)
