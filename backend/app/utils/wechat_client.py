"""微信开放平台 HTTP 客户端：access_token 缓存 + 内容安全检查。

仅内容审核链路使用；登录换 session 的 jscode2session 在 services/auth.py。
"""
import logging
from pathlib import Path

import httpx

from app.config import settings
from app.utils.redis import redis_client

logger = logging.getLogger(__name__)

WECHAT_API_BASE = "https://api.weixin.qq.com"
REDIS_TOKEN_KEY = "wx:access_token"
# 提前 5 分钟过期，避免边界失效
TOKEN_EARLY_EXPIRY_SECONDS = 300
HTTP_TIMEOUT = 10.0
# img_sec_check 单图上限 1M
IMAGE_MAX_BYTES = 1024 * 1024

# 微信错误码语义
ERRCODE_RATE_LIMIT = 45009  # 调用超频
ERRCODE_CONTENT_RISKY = 87014  # 内容违规（v1 语义，v2 用 suggest 表达，双保险都判）


class WechatClientError(Exception):
    """微信 API 调用失败（网络/未授权/配额）。"""


async def get_access_token(force_refresh: bool = False) -> str:
    """获取 access_token（stable_token），Redis 缓存。

    Raises:
        WechatClientError: 微信侧错误或网络失败。
    """
    if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
        raise WechatClientError("WECHAT_APP_ID/SECRET 未配置")

    if not force_refresh:
        cached = await redis_client.get(REDIS_TOKEN_KEY)
        if cached:
            return cached

    async with httpx.AsyncClient(trust_env=False, timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{WECHAT_API_BASE}/cgi-bin/stable_token",
            json={
                "grant_type": "client_credential",
                "appid": settings.WECHAT_APP_ID,
                "secret": settings.WECHAT_APP_SECRET,
                "force_refresh": force_refresh,
            },
        )
    data = resp.json()
    if data.get("errcode"):
        raise WechatClientError(f"stable_token 失败: {data}")

    token = data["access_token"]
    ttl = max(int(data.get("expires_in", 7200)) - TOKEN_EARLY_EXPIRY_SECONDS, 60)
    await redis_client.set(REDIS_TOKEN_KEY, token, ex=ttl)
    return token


async def msg_sec_check(content: str, openid: str, scene: int = 2) -> dict:
    """文本内容安全 v2（同步）。返回 {"errcode":0, "result":{"suggest":...,"label":...}, "trace_id":...}。

    Raises:
        WechatClientError: 网络/配额/鉴权错误。
    """
    token = await get_access_token()
    async with httpx.AsyncClient(trust_env=False, timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{WECHAT_API_BASE}/wxa/msg_sec_check?access_token={token}",
            json={"content": content, "version": 2, "scene": scene, "openid": openid},
        )
    data = resp.json()
    errcode = data.get("errcode", 0)
    # 40001/42001: token 失效，强刷一次后重试
    if errcode in (40001, 42001):
        token = await get_access_token(force_refresh=True)
        async with httpx.AsyncClient(trust_env=False, timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{WECHAT_API_BASE}/wxa/msg_sec_check?access_token={token}",
                json={"content": content, "version": 2, "scene": scene, "openid": openid},
            )
        data = resp.json()
        errcode = data.get("errcode", 0)
    if errcode == ERRCODE_RATE_LIMIT:
        raise WechatClientError(f"msg_sec_check 配额超限: {data}")
    if errcode not in (0,):
        raise WechatClientError(f"msg_sec_check 失败: {data}")
    return data


async def img_sec_check(image_bytes: bytes, filename: str) -> dict:
    """图片内容安全（同步 multipart 版）。图片须 ≤1M。

    Raises:
        WechatClientError: 网络/配额/鉴权错误。
    """
    token = await get_access_token()
    async with httpx.AsyncClient(trust_env=False, timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            f"{WECHAT_API_BASE}/wxa/img_sec_check?access_token={token}",
            files={"media": (filename, image_bytes)},
        )
    data = resp.json()
    errcode = data.get("errcode", 0)
    if errcode in (40001, 42001):
        token = await get_access_token(force_refresh=True)
        async with httpx.AsyncClient(trust_env=False, timeout=HTTP_TIMEOUT) as client:
            resp = await client.post(
                f"{WECHAT_API_BASE}/wxa/img_sec_check?access_token={token}",
                files={"media": (filename, image_bytes)},
            )
        data = resp.json()
        errcode = data.get("errcode", 0)
    if errcode == ERRCODE_RATE_LIMIT:
        raise WechatClientError(f"img_sec_check 配额超限: {data}")
    if errcode not in (0,):
        raise WechatClientError(f"img_sec_check 失败: {data}")
    return data


async def load_image_bytes(url: str) -> tuple[bytes, str]:
    """Read legacy static images only, with containment and a pre-read size cap.

    New media uses opaque IDs and private storage; outbound URL fetching is forbidden.
    """
    import asyncio
    from urllib.parse import unquote

    if not url.startswith("/static/"):
        raise WechatClientError("仅允许本站受控媒体")
    relative = unquote(url[len("/static/"):])
    base = Path(settings.STATIC_BASE_DIR).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise WechatClientError("非法或不存在的媒体")
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise WechatClientError("非法媒体类型")
    if path.stat().st_size > IMAGE_MAX_BYTES:
        raise WechatClientError("图片超过大小限制")
    def read_limited():
        with path.open("rb") as handle:
            return handle.read(IMAGE_MAX_BYTES + 1)
    data = await asyncio.to_thread(read_limited)
    if len(data) > IMAGE_MAX_BYTES:
        raise WechatClientError("图片超过大小限制")
    return data, path.name
