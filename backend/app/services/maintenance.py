"""系统维护服务：静态孤儿文件与未绑定媒体清理。"""
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.post import Post
from app.models.banner import Banner
from app.models.activity import Activity
from app.services.media import cleanup_unbound_media


async def cleanup_orphan_static_files(
    db: AsyncSession,
    max_age_seconds: int = 86400,
    dry_run: bool = False,
) -> dict:
    """清理本地 /static/ 目录下无任何活跃帖子、广告或活动引用的孤儿文件（默认超过24小时）。

    返回:
        {"orphan_files_removed": int, "bytes_freed": int, "unbound_media_removed": int}
    """
    base_dir = Path(settings.STATIC_BASE_DIR)
    posts_dir = base_dir / "posts"

    # 1. 汇总数据库中所有合法的相对静态引用路径
    # 活跃帖子 (status != -2)
    post_rows = (await db.execute(select(Post.images).where(Post.status != -2))).scalars().all()
    referenced_urls: set[str] = set()
    for img_list in post_rows:
        if isinstance(img_list, list):
            for url in img_list:
                if isinstance(url, str):
                    referenced_urls.add(url.strip())

    # 活跃 Banner
    banner_rows = (await db.execute(select(Banner.image_url))).scalars().all()
    for url in banner_rows:
        if url:
            referenced_urls.add(url.strip())

    # 活跃 Activity
    activity_rows = (await db.execute(select(Activity.image_url))).scalars().all()
    for url in activity_rows:
        if url:
            referenced_urls.add(url.strip())

    now = time.time()
    orphan_files_removed = 0
    bytes_freed = 0

    if posts_dir.exists() and posts_dir.is_dir():
        for file_path in posts_dir.rglob("*"):
            if not file_path.is_file():
                continue
            # 必须超过安全时间，防止正在提交中的发帖图片被误杀
            try:
                mtime = file_path.stat().st_mtime
                if now - mtime < max_age_seconds:
                    continue
            except OSError:
                continue

            rel_path = file_path.relative_to(base_dir).as_posix()
            public_url = f"/static/{rel_path}"

            if public_url not in referenced_urls:
                try:
                    file_size = file_path.stat().st_size
                    if not dry_run:
                        file_path.unlink(missing_ok=True)
                    orphan_files_removed += 1
                    bytes_freed += file_size
                except OSError:
                    pass

    # 2. 联动清理私有未绑定媒体资产
    unbound_media_removed = 0
    try:
        unbound_media_removed = await cleanup_unbound_media(db)
    except Exception:
        pass

    return {
        "orphan_files_removed": orphan_files_removed,
        "bytes_freed": bytes_freed,
        "unbound_media_removed": unbound_media_removed,
    }
