"""A reversible publish switch keeps read and account-security operations available."""
from fastapi import HTTPException
from app.config import settings
from app.utils import redis as redis_module

PUBLISH_KEY = "runtime:publishing_enabled"

async def publishing_enabled() -> bool:
    value = await redis_module.redis_client.get(PUBLISH_KEY)
    return settings.PUBLISHING_ENABLED and value != "false"

async def require_publishing():
    if not await publishing_enabled():
        raise HTTPException(503, "投稿暂时关闭，已发布内容仍可浏览；请稍后再试")
