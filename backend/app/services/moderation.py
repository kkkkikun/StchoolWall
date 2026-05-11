"""异步内容审核后台任务

SchoolWall.md Phase 3 Section 1:
- 使用 FastAPI BackgroundTasks 调用
- 仅传递序列化参数 (post_id)，不传递 ORM 对象
- 重新查询数据库，执行审核，更新状态
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.post import Post
from app.utils.moderation import check_images, check_text


async def check_post_images(post_id: int) -> None:
    """后台任务：审核帖子图片并更新状态

    注意：此函数在 BackgroundTasks 中执行，请求已结束，必须创建新的 DB session。
    """
    async with async_session() as db:
        result = await db.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            return

        # 只处理待审核状态
        if post.status != 0:
            return

        # 无图片或图片审核通过 → 正常
        # 文本也检查（可选）
        images_ok = await check_images(post.images or [])
        text_ok = await check_text(post.content)

        if images_ok and text_ok:
            post.status = 1  # 正常展示
        else:
            post.status = -1  # 封禁

        await db.commit()
