"""Production regressions: private media, transaction boundaries and worker fencing."""
import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image
from sqlalchemy import func, select, update

from app.config import settings
from app.models.interaction import Footprint
from app.models.job import Job
from app.models.media import MediaAsset
from app.models.notification import Notification
from app.models.party import Party
from app.models.post import Post
from app.services.jobs import claim_job, enqueue_job, finish_job
from app.services.media import bind_media, create_media, normalize_image
from app.services.notification import list_notifications
from app.utils.moderation import check_text
from tests.conftest import TestSession


def _jpeg(exif=False):
    image = Image.new("RGB", (16, 12), (10, 20, 30))
    output = io.BytesIO()
    metadata = Image.Exif()
    if exif:
        metadata[270] = "private GPS-like metadata"
    image.save(output, "JPEG", exif=metadata)
    return output.getvalue()


@pytest.fixture
def private_storage(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    monkeypatch.setattr(settings, "STATIC_BASE_DIR", str(static))
    monkeypatch.setattr(settings, "PRIVATE_MEDIA_DIR", str(tmp_path / "private"))
    monkeypatch.setattr(settings, "STORAGE_PROVIDER", "local")
    return static


def test_images_decode_and_strip_metadata():
    cleaned = normalize_image(_jpeg(exif=True))
    with Image.open(io.BytesIO(cleaned)) as image:
        assert image.size == (16, 12)
        assert not image.getexif()
    with pytest.raises(ValueError):
        normalize_image(b"<script>not an image</script>")


def test_image_pixel_limit(monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_MAX_PIXELS", 100)
    with pytest.raises(ValueError, match="像素"):
        normalize_image(_jpeg())


@pytest.mark.asyncio
async def test_moderation_missing_provider_keeps_manual_queue(monkeypatch):
    monkeypatch.setattr(settings, "TENCENT_SECRET_ID", "")
    monkeypatch.setattr(settings, "TENCENT_SECRET_KEY", "")
    assert (await check_text("正常内容")).verdict == "review"


@pytest.mark.asyncio
async def test_legacy_reader_never_escapes_static(private_storage):
    from app.utils.wechat_client import WechatClientError, load_image_bytes
    outside = private_storage.parent / "secret.jpg"
    outside.write_bytes(_jpeg())
    for path in ("/static/../secret.jpg", "/static/%2e%2e/secret.jpg", "http://127.0.0.1/x"):
        with pytest.raises(WechatClientError):
            await load_image_bytes(path)
    (private_storage / "safe.jpg").write_bytes(_jpeg())
    assert (await load_image_bytes("/static/safe.jpg"))[0] == _jpeg()


@pytest.mark.asyncio
async def test_upload_is_private_owned_and_transactional(student_user, guest_user, private_storage):
    async with TestSession() as db:
        asset = await create_media(db, student_user, "posts", _jpeg())
        media_id = asset.id
        assert asset.status == "quarantine" and asset.public_path is None
        assert not list(private_storage.rglob("*.jpg"))
        assert await db.scalar(select(func.count()).select_from(Job)) == 1
        await db.commit()
    async with TestSession() as db:
        with pytest.raises(ValueError, match="不属于"):
            await bind_media(db, guest_user.id, [media_id], "posts", "post", 1)
        with pytest.raises(ValueError, match="用途"):
            await bind_media(db, student_user.id, [media_id], "avatars", "profile", 1)


@pytest.mark.asyncio
async def test_bound_media_keeps_the_order_the_author_chose(student_user, private_storage):
    """用户选择的图片先后顺序必须贯穿绑定、读取与发布（position 列）。"""
    from app.services.media import entity_media, publish_entity_media

    async with TestSession() as db:
        assets = [await create_media(db, student_user, "posts", _jpeg()) for _ in range(3)]
        # 故意用非签发顺序绑定：模拟并发上传完成顺序与选择顺序不一致
        chosen = [assets[2].id, assets[0].id, assets[1].id]
        await db.commit()

    async with TestSession() as db:
        bound = await bind_media(db, student_user.id, chosen, "posts", "post", 77)
        assert [asset.id for asset in bound] == chosen
        assert [asset.position for asset in bound] == [0, 1, 2]
        await db.commit()

    async with TestSession() as db:
        stored = await entity_media(db, "post", 77)
        assert [asset.id for asset in stored] == chosen
        urls = await publish_entity_media(db, "post", 77)
        assert urls == [f"/api/v1/upload/media/{media_id}/content" for media_id in chosen]
        await db.commit()


@pytest.mark.asyncio
async def test_job_rollback_and_dedupe():
    async with TestSession() as db:
        await enqueue_job(db, "moderate_post", {"post_id": 1}, "rollback")
        await db.rollback()
        assert await db.scalar(select(func.count()).select_from(Job)) == 0
        first = await enqueue_job(db, "moderate_post", {"post_id": 1}, "same")
        second = await enqueue_job(db, "moderate_post", {"post_id": 1}, "same")
        assert first == second
        await db.commit()


@pytest.mark.asyncio
async def test_expired_worker_lease_is_fenced():
    async with TestSession() as db:
        await enqueue_job(db, "moderate_post", {"post_id": 1}, "lease")
        await db.commit()
        old = await claim_job(db)
        assert old and old.attempts == 1
    async with TestSession() as db:
        await db.execute(update(Job).where(Job.id == old.id).values(
            lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await db.commit()
        current = await claim_job(db)
        assert current and current.attempts == 2 and current.lease_token != old.lease_token
    async with TestSession() as db:
        assert not await finish_job(db, old)
        assert await finish_job(db, current)
        assert (await db.get(Job, current.id)).status == "succeeded"


@pytest.mark.asyncio
async def test_only_one_worker_claims_a_job():
    async with TestSession() as db:
        await enqueue_job(db, "moderate_post", {"post_id": 1}, "one-claim")
        await db.commit()
    async def claim():
        async with TestSession() as db:
            return await claim_job(db)
    claimed = await asyncio.gather(claim(), claim())
    assert sum(job is not None for job in claimed) == 1


@pytest.mark.asyncio
async def test_closed_party_cannot_be_joined(student_user):
    from app.services.party import join_party
    async with TestSession() as db:
        party = Party(user_id=student_user.id, type="group", category="自习",
                      title="关闭", content="关闭", total=10, status=-1)
        db.add(party)
        await db.commit()
        assert await join_party(db, student_user, party.id) is None
        assert party.joined_count == 0 and party.status == -1


@pytest.mark.asyncio
async def test_notification_cursor_survives_read_flag_changes(student_user, admin_user):
    async with TestSession() as db:
        rows = [Notification(user_id=student_user.id, actor_id=admin_user.id,
                             type="like", is_read=flag) for flag in (False, True)]
        db.add_all(rows)
        await db.commit()
        page, cursor, more = await list_notifications(db, student_user, limit=1)
        assert more and page[0]["id"] == rows[1].id
        rows[0].is_read, rows[1].is_read = True, False
        await db.commit()
        page2, _, _ = await list_notifications(db, student_user, cursor=cursor, limit=1)
        assert page2[0]["id"] == rows[0].id


@pytest.mark.asyncio
async def test_concurrent_footprint_upsert_has_one_row(student_user):
    from app.services.interaction import record_footprint
    async with TestSession() as db:
        post = Post(user_id=student_user.id, post_type="general", content="足迹", status=1)
        db.add(post)
        await db.commit()
        post_id = post.id
    async def visit():
        async with TestSession() as db:
            await record_footprint(db, student_user, post_id)
    await asyncio.gather(visit(), visit())
    async with TestSession() as db:
        assert await db.scalar(select(func.count()).select_from(Footprint)) == 1


@pytest.mark.asyncio
async def test_machine_result_cannot_overwrite_admin_decision(student_user, monkeypatch):
    import app.services.moderation as moderation
    from app.utils.moderation import ModerationResult
    async with TestSession() as db:
        post = Post(user_id=student_user.id, post_type="general", content="待审", status=0)
        db.add(post)
        await db.commit()
        post_id = post.id
    monkeypatch.setattr(moderation, "async_session", TestSession)
    async def decide_after_admin(*args):
        async with TestSession() as db:
            await db.execute(update(Post).where(Post.id == post_id).values(status=-1))
            await db.commit()
        return ModerationResult("pass")
    monkeypatch.setattr(moderation, "check_text", decide_after_admin)
    with pytest.raises(moderation.ModerationRetry):
        await moderation.check_post_moderation(post_id)
    async with TestSession() as db:
        assert (await db.get(Post, post_id)).status == -1


@pytest.mark.asyncio
async def test_clean_comment_is_queued_without_public_counter(student_user, admin_user):
    from app.services.interaction import create_comment
    async with TestSession() as db:
        post = Post(user_id=admin_user.id, post_type="general", content="公开帖", status=1)
        db.add(post)
        await db.commit()
        result = await create_comment(db, student_user, post.id, "请审核这条评论")
        assert result["status"] == 0 and result["comment_count"] == 0
        job = (await db.execute(select(Job).where(Job.kind == "moderate_comment"))).scalar_one()
        assert job.payload["comment_id"] == result["id"]
        assert await db.scalar(select(func.count()).select_from(Notification)) == 0


@pytest.mark.asyncio
async def test_worker_failure_retries_then_moves_to_dead_letter(monkeypatch):
    import app.worker as worker
    monkeypatch.setattr(worker, "async_session", TestSession)
    async def unavailable(job):
        raise RuntimeError("provider failure must never be stored verbatim")
    monkeypatch.setattr(worker, "dispatch_job", unavailable)
    async with TestSession() as db:
        job_id = await enqueue_job(db, "moderate_post", {"post_id": 1}, "retry-dead")
        await db.execute(update(Job).where(Job.id == job_id).values(max_attempts=2))
        await db.commit()
    assert await worker.run_once()
    async with TestSession() as db:
        job = await db.get(Job, job_id)
        assert job.status == "pending" and job.attempts == 1 and job.last_error == "RuntimeError"
        await db.execute(update(Job).where(Job.id == job_id).values(available_at=datetime.now(timezone.utc)))
        await db.commit()
    assert await worker.run_once()
    async with TestSession() as db:
        job = await db.get(Job, job_id)
        assert job.status == "dead" and job.attempts == 2
        assert job.lease_token is None


@pytest.mark.asyncio
async def test_media_content_is_inaccessible_before_review_and_after_rejection(client, student_user, private_storage):
    async with TestSession() as db:
        asset = await create_media(db, student_user, "posts", _jpeg(exif=True))
        media_id = asset.id
        await db.commit()
    path = f"/api/v1/upload/media/{media_id}/content"
    assert (await client.get(path)).status_code == 404
    async with TestSession() as db:
        await db.execute(update(MediaAsset).where(MediaAsset.id == media_id).values(status="approved"))
        await db.commit()
    response = await client.get(path)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    with Image.open(io.BytesIO(response.content)) as image:
        assert not image.getexif()
    async with TestSession() as db:
        await db.execute(update(MediaAsset).where(MediaAsset.id == media_id).values(status="rejected"))
        await db.commit()
    assert (await client.get(path)).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["comment", "party"])
async def test_admin_audit_failure_rolls_back_state_counters_and_notification(
    target, client, console_headers, student_user, admin_user, monkeypatch,
):
    import app.routers.admin as router
    from app.models.interaction import Comment
    async with TestSession() as db:
        post = Post(user_id=admin_user.id, post_type="general", content="审计事务", status=1)
        party = Party(user_id=student_user.id, type="group", category="自习",
                      title="审计事务", content="事务", total=10, status=0)
        db.add_all([post, party])
        await db.flush()
        comment = Comment(user_id=student_user.id, post_id=post.id, content="待审评论", status=0)
        db.add(comment)
        await db.commit()
        post_id, party_id, comment_id = post.id, party.id, comment.id
    async def audit_unavailable(*args, **kwargs):
        raise RuntimeError("simulated audit failure")
    monkeypatch.setattr(router, "log_admin_action", audit_unavailable)
    path = f"/api/v1/admin/comments/{comment_id}/status" if target == "comment" else f"/api/v1/admin/parties/{party_id}/status"
    response = await client.put(path, params={"status": 1}, headers=console_headers)
    assert response.status_code == 500
    async with TestSession() as db:
        assert (await db.get(Comment, comment_id)).status == 0
        assert (await db.get(Party, party_id)).status == 0
        assert (await db.get(Post, post_id)).comment_count == 0
        assert await db.scalar(select(func.count()).select_from(Notification)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ["closed_post", "blocked"])
async def test_manual_comment_approval_obeys_post_visibility_and_blocking(
    condition, client, console_headers, student_user, admin_user,
):
    from app.models.interaction import Comment
    from app.models.block import UserBlock
    async with TestSession() as db:
        post = Post(user_id=admin_user.id, post_type="general", content="不可发布评论",
                    status=-1 if condition == "closed_post" else 1)
        db.add(post)
        await db.flush()
        comment = Comment(user_id=student_user.id, post_id=post.id, content="待审评论", status=0)
        db.add(comment)
        if condition == "blocked":
            db.add(UserBlock(blocker_id=admin_user.id, blocked_id=student_user.id))
        await db.commit()
        post_id, comment_id = post.id, comment.id
    response = await client.put(f"/api/v1/admin/comments/{comment_id}/status",
                                params={"status": 1}, headers=console_headers)
    assert response.status_code == 400
    async with TestSession() as db:
        assert (await db.get(Comment, comment_id)).status == 0
        assert (await db.get(Post, post_id)).comment_count == 0
        assert await db.scalar(select(func.count()).select_from(Notification)) == 0
