"""Persistent runtime switches for beta operations and account access."""
from fastapi import HTTPException

from app.config import settings
from app.utils import redis as redis_module

PUBLISH_KEY = "runtime:publishing_enabled"
CONTROL_DEFAULTS = {
    "publishing_enabled": settings.PUBLISHING_ENABLED,
    "moderation_enabled": True,
    "sensitive_words_enabled": True,
    "registration_enabled": True,
    "guest_posting_enabled": False,
    "guest_interaction_enabled": False,
}


def _key(name: str) -> str:
    return f"runtime:{name}"


def _decode(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value == "true"


async def get_runtime_controls() -> dict[str, bool]:
    names = list(CONTROL_DEFAULTS)
    values = await redis_module.redis_client.mget([_key(name) for name in names])
    controls = {name: _decode(value, CONTROL_DEFAULTS[name]) for name, value in zip(names, values)}
    controls["publishing_enabled"] = settings.PUBLISHING_ENABLED and controls["publishing_enabled"]
    return controls


async def update_runtime_controls(changes: dict[str, bool]) -> None:
    if changes:
        await redis_module.redis_client.mset({_key(name): "true" if value else "false"
                                               for name, value in changes.items()})


async def _enabled(name: str) -> bool:
    value = await redis_module.redis_client.get(_key(name))
    return _decode(value, CONTROL_DEFAULTS[name])


async def publishing_enabled() -> bool:
    return settings.PUBLISHING_ENABLED and await _enabled("publishing_enabled")


async def moderation_enabled() -> bool:
    return await _enabled("moderation_enabled")


async def sensitive_words_enabled() -> bool:
    return await _enabled("sensitive_words_enabled")


async def guest_posting_enabled() -> bool:
    return await _enabled("guest_posting_enabled")


async def guest_interaction_enabled() -> bool:
    return await _enabled("guest_interaction_enabled")


async def require_publishing():
    if not await publishing_enabled():
        raise HTTPException(503, "投稿暂时关闭，已发布内容仍可浏览；请稍后再试")


async def require_registration():
    if not await _enabled("registration_enabled"):
        raise HTTPException(403, "内测注册暂未开放，请使用已有账号登录")
