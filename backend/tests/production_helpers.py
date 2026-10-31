"""Helpers exercise real moderation handlers while mocking only external decisions."""
import io
from unittest.mock import patch

from PIL import Image
from sqlalchemy import select

from app.models.interaction import Comment
from app.utils.moderation import ModerationResult
from tests.conftest import TestSession


def image_bytes(format="JPEG"):
    result = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(result, format)
    return result.getvalue()


async def approve_comments():
    import app.services.moderation as service
    async def passed(*args):
        return ModerationResult("pass")
    with patch.object(service, "async_session", TestSession), patch.object(service, "check_text", passed):
        async with TestSession() as db:
            ids = list((await db.execute(select(Comment.id).where(Comment.status == 0))).scalars())
        for comment_id in ids:
            await service.check_comment_moderation(comment_id)


async def approve_party(party_id):
    import app.services.moderation as service
    async def passed(*args):
        return ModerationResult("pass")
    with patch.object(service, "async_session", TestSession), patch.object(service, "check_text", passed):
        await service.check_party_moderation(party_id)


async def approve_profile(job_id):
    import uuid
    import app.services.moderation as service
    from app.models.job import Job
    async def passed(*args):
        return ModerationResult("pass")
    async with TestSession() as db:
        payload = (await db.get(Job, uuid.UUID(str(job_id)))).payload
    with patch.object(service, "async_session", TestSession), patch.object(service, "check_text", passed), patch.object(service, "check_image_data", passed):
        await service.check_profile_moderation(payload)
