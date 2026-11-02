"""反馈截图的私有存储。

与公开媒体（media_assets）完全隔离：截图可能包含测试人员的环境信息，
只有管理台鉴权接口能读取，猜到路径也无法直接访问。
"""
import asyncio
import hashlib
import re
import uuid
from pathlib import Path

from app.config import settings
from app.services.media import normalize_image

MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
MAX_SCREENSHOTS = 5
_KEY_PATTERN = re.compile(r"^feedback/[0-9]+/[0-9a-f]{32}\.jpg$")


def _base_dir() -> Path:
    configured = Path(getattr(settings, "FEEDBACK_PRIVATE_DIR", "private-feedback"))
    static = Path(settings.STATIC_BASE_DIR).resolve()
    base = configured.resolve() if configured.is_absolute() else (static.parent / configured).resolve()
    if base.is_relative_to(static):
        raise ValueError("反馈截图目录不能位于公开静态目录内")
    return base


def _path(key: str) -> Path:
    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError("非法反馈截图标识")
    path = (_base_dir() / key).resolve()
    if not path.is_relative_to(_base_dir()):
        raise ValueError("非法反馈截图路径")
    return path


def screenshot_key(feedback_id: int, content: bytes) -> str:
    """按内容哈希定名，重复上传同一张图不会产生冗余文件。"""
    return f"feedback/{feedback_id}/{uuid.uuid5(uuid.NAMESPACE_URL, hashlib.sha256(content).hexdigest()).hex}.jpg"


async def save_screenshot(feedback_id: int, content: bytes) -> dict:
    if not content:
        raise ValueError("截图内容为空")
    if len(content) > MAX_SCREENSHOT_BYTES:
        raise ValueError("截图超过 5MB 限制")
    # 复用媒体归一化：解码为真实像素并重编码 JPEG，顺带抹掉 EXIF 里的拍摄信息。
    normalized = await asyncio.to_thread(normalize_image, content)
    key = screenshot_key(feedback_id, normalized)

    def save() -> None:
        path = _path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(normalized)

    await asyncio.to_thread(save)
    return {"path": key, "size": len(normalized), "content_type": "image/jpeg",
            "sha256": hashlib.sha256(normalized).hexdigest()}


async def read_screenshot(key: str) -> bytes:
    def read() -> bytes:
        path = _path(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    return await asyncio.to_thread(read)


async def delete_screenshot(key: str) -> None:
    def remove() -> None:
        try:
            _path(key).unlink(missing_ok=True)
        except ValueError:
            pass

    await asyncio.to_thread(remove)
