"""Durable moderation handlers. A worker may retry safely after any crash."""
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.interaction import Comment
from app.models.media import MediaAsset
from app.models.notification import Notification
from app.models.party import Party
from app.models.post import Post
from app.models.user import User
from app.services.blocks import blocked_between
from app.services.media import entity_media, media_bytes, media_url, publish_entity_media, reject_entity_media
from app.services.moderation_record import add_moderation_record
from app.services.sensitive_word import load_active_words
from app.utils.local_rules import check_text_local
from app.utils.moderation import ModerationResult, _strictest, check_image_data, check_images, check_text, _is_configured

FREQ_WINDOW_MINUTES = 10
FREQ_MAX_POSTS = 3


class ModerationRetry(RuntimeError):
    pass


class ManualReviewRequired(RuntimeError):
    pass


class ContentRejected(RuntimeError):
    pass


async def _check_frequency(db: AsyncSession, user_id) -> ModerationResult:
    since = datetime.now(timezone.utc) - timedelta(minutes=FREQ_WINDOW_MINUTES)
    count = await db.scalar(select(func.count()).select_from(Post).where(
        Post.user_id == user_id, Post.created_at >= since,
    )) or 0
    return ModerationResult("review", reason="posting_frequency") if count >= FREQ_MAX_POSTS else ModerationResult("pass")


async def _text_verdict(db: AsyncSession, content: str) -> tuple[ModerationResult, list[str], ModerationResult, ModerationResult]:
    local, matched = check_text_local(content, await load_active_words(db))
    if local.verdict == "reject":
        return local, matched, local, ModerationResult("pass")
    provider = await check_text(content, "")
    if provider.verdict == "error":
        raise ModerationRetry("provider_unavailable")
    return _strictest([local, provider]), matched, local, provider


async def _media_verdict(db: AsyncSession, entity_type: str, entity_id: int,
                         legacy_images: list[str] | None = None) -> ModerationResult:
    results = []
    assets = await entity_media(db, entity_type, entity_id)
    for asset in assets:
        if asset.status in {"rejected", "deleted"}:
            results.append(ModerationResult("reject", reason="media_rejected"))
        elif asset.status == "approved":
            results.append(ModerationResult("pass"))
        else:
            results.append(await check_image_data(await media_bytes(asset)))
    if legacy_images and not assets:
        results.append(await check_images(legacy_images))
    result = _strictest(results)
    if result.verdict == "error":
        raise ModerationRetry("provider_unavailable")
    return result


async def check_post_moderation(post_id: int) -> None:
    async with async_session() as db:
        post = await db.get(Post, post_id)
        if not post or post.status != 0:
            return
        snapshot = post.updated_at
        text_result, matched, local_result, provider_result = await _text_verdict(db, post.content)
        media_result = (ModerationResult("pass") if local_result.verdict == "reject"
                        else await _media_verdict(db, "post", post_id, post.images or []))
        rule_result = _strictest([local_result, await _check_frequency(db, post.user_id)])
        result = _strictest([text_result, media_result, rule_result])
        add_moderation_record(db, post_id, "rule", rule_result, matched=matched or None)
        if local_result.verdict != "reject" and _is_configured():
            add_moderation_record(db, post_id, "tencent", _strictest([provider_result, media_result]))
        if result.verdict == "review":
            await db.commit()
            raise ManualReviewRequired("manual_review")
        status = 1 if result.verdict == "pass" else -1
        changed = await db.execute(update(Post).where(
            Post.id == post_id, Post.status == 0, Post.updated_at == snapshot,
        ).values(status=status))
        if changed.rowcount != 1:
            await db.rollback()
            raise ModerationRetry("content_changed")
        if status == 1:
            urls = await publish_entity_media(db, "post", post_id)
            if urls:
                await db.execute(update(Post).where(Post.id == post_id).values(images=urls))
        else:
            await reject_entity_media(db, "post", post_id)
            db.add(Notification(user_id=post.user_id, actor_id=post.user_id,
                                type="moderation", post_id=post_id))
        await db.commit()


async def check_media_moderation(media_id: str) -> None:
    async with async_session() as db:
        asset = await db.get(MediaAsset, uuid.UUID(media_id))
        if not asset or asset.status != "quarantine":
            return
        snapshot = asset.updated_at
        result = await check_image_data(await media_bytes(asset))
        if result.verdict == "error":
            raise ModerationRetry("provider_unavailable")
        if result.verdict == "review":
            raise ManualReviewRequired("manual_review")
        approved = result.verdict == "pass"
        await db.execute(update(MediaAsset).where(
            MediaAsset.id == asset.id, MediaAsset.status == "quarantine", MediaAsset.updated_at == snapshot,
        ).values(status="approved" if approved else "rejected",
                 public_path=media_url(asset) if approved else None))
        await db.commit()


async def check_comment_moderation(comment_id: int) -> None:
    async with async_session() as db:
        comment = await db.get(Comment, comment_id)
        if not comment or comment.status != 0:
            return
        content_snapshot = comment.content
        result, matched, _, _ = await _text_verdict(db, content_snapshot)
        add_moderation_record(db, comment.post_id, "tencent", result,
                              matched=matched or None, comment_id=comment_id)
        if result.verdict == "review":
            await db.commit()
            raise ManualReviewRequired("manual_review")
        # Locks serialize machine decisions with admin transitions.
        current = (await db.execute(select(Comment).where(
            Comment.id == comment_id,
        ).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if current.status != 0 or current.content != content_snapshot:
            await db.rollback()
            return
        post = (await db.execute(select(Post).where(Post.id == current.post_id).with_for_update())).scalar_one()
        if post.status != 1 or await blocked_between(db, current.user_id, post.user_id):
            current.status = -1
            await db.commit()
            return
        current.status = 1 if result.verdict == "pass" else -1
        if current.status == 1:
            post.comment_count = (post.comment_count or 0) + 1
            if post.user_id != current.user_id:
                db.add(Notification(user_id=post.user_id, actor_id=current.user_id, type="comment",
                                    post_id=post.id, comment_id=current.id))
        await db.commit()


async def check_party_moderation(party_id: int) -> None:
    async with async_session() as db:
        party = await db.get(Party, party_id)
        if not party or party.status != 0:
            return
        snapshot = (party.title, party.content, party.location)
        result, _, _, _ = await _text_verdict(db, " ".join(value or "" for value in snapshot))
        if result.verdict == "review":
            raise ManualReviewRequired("manual_review")
        changed = await db.execute(update(Party).where(
            Party.id == party_id, Party.status == 0,
            Party.title == snapshot[0], Party.content == snapshot[1],
            Party.location.is_(None) if snapshot[2] is None else Party.location == snapshot[2],
        ).values(status=1 if result.verdict == "pass" else -1))
        if changed.rowcount != 1:
            await db.rollback()
            raise ModerationRetry("content_changed")
        await db.commit()


async def check_profile_moderation(payload: dict) -> None:
    async with async_session() as db:
        user = await db.get(User, uuid.UUID(payload["user_id"]))
        expected = datetime.fromisoformat(payload["expected_updated_at"])
        if not user or user.status != 1 or user.updated_at != expected:
            return
        updates = payload["updates"]
        result, _, _, _ = await _text_verdict(db, " ".join(
            str(updates.get(key) or "") for key in ("nickname", "bio", "wechat_id")))
        assets = []
        for field, media_id in payload.get("media", {}).items():
            asset = await db.get(MediaAsset, uuid.UUID(media_id))
            if not asset or asset.owner_id != user.id or asset.status in {"rejected", "deleted"}:
                return
            assets.append((field, asset))
            if asset.status != "approved":
                image_result = await check_image_data(await media_bytes(asset))
                if image_result.verdict == "error":
                    raise ModerationRetry("provider_unavailable")
                result = _strictest([result, image_result])
        if result.verdict == "review":
            raise ManualReviewRequired("manual_review")
        if result.verdict == "reject":
            raise ContentRejected("profile_rejected")
        await apply_profile_update(db, payload)
        await db.commit()


async def apply_profile_update(db: AsyncSession, payload: dict) -> bool:
    """Apply a machine or administrator approved draft in the caller's transaction."""
    user_id = uuid.UUID(payload["user_id"])
    expected = datetime.fromisoformat(payload["expected_updated_at"])
    updates = {key: value for key, value in payload.get("updates", {}).items()
               if key in {"nickname", "bio", "wechat_id", "avatar_url", "banner_url"}}
    assets = []
    for field, media_id in payload.get("media", {}).items():
        if field not in {"avatar_url", "banner_url"}:
            raise ValueError("非法资料媒体字段")
        asset = await db.get(MediaAsset, uuid.UUID(media_id))
        purpose = "avatars" if field == "avatar_url" else "banners"
        if not asset or asset.owner_id != user_id or asset.purpose != purpose or asset.status in {"rejected", "deleted"}:
            raise ValueError("资料图片不可用")
        assets.append(asset)
        updates[field] = media_url(asset)
    changed = await db.execute(update(User).where(
        User.id == user_id, User.status == 1, User.updated_at == expected,
    ).values(**updates))
    if changed.rowcount != 1:
        return False
    for asset in assets:
        asset.status, asset.public_path, asset.entity_type = "approved", media_url(asset), "profile"
    return True
