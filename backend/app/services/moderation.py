"""异步内容审核后台任务

发布学生帖后由 FastAPI BackgroundTasks 调用：
- 仅传序列化参数 (post_id)，不传 ORM 对象（请求已结束）
- 新开 DB session 重查帖子与作者（msg_sec_check v2 需要 openid）
- verdict 分流：pass→1 / reject→-1+通知 / review→保持0等人工 / error→重试后降级
"""
import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.post import Post
from app.models.user import User
from app.services.notification import create_system_notification
from app.utils.moderation import ModerationResult, check_images, check_text

logger = logging.getLogger(__name__)

# 网络故障重试次数与退避（秒）
MAX_RETRIES = 3
BACKOFF_SECONDS = [2, 4]


async def _backoff_sleep(seconds: float) -> None:
    """退避等待（测试里可 monkeypatch 置零）。"""
    await asyncio.sleep(seconds)


def _combined_verdict(text_r: ModerationResult, image_r: ModerationResult) -> ModerationResult:
    """文本与图片取更严的一方。"""
    from app.utils.moderation import _strictest
    return _strictest([text_r, image_r])


async def check_post_moderation(post_id: int) -> None:
    """后台任务：审核帖子并更新状态。

    注意：此函数在 BackgroundTasks 中执行，请求已结束，必须创建新的 DB session。
    """
    async with async_session() as db:
        result = await db.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            return

        # 幂等：只处理待审核状态（admin 手工过审/并发任务不覆盖）
        if post.status != 0:
            return

        # v2 文本审核需要作者 openid
        author = (await db.execute(
            select(User).where(User.id == post.user_id)
        )).scalar_one_or_none()
        openid = author.openid if author else ""

        attempt = 0
        while True:
            text_r = await check_text(post.content, openid)
            image_r = await check_images(post.images or [])
            verdict = _combined_verdict(text_r, image_r)

            if verdict.verdict != "error":
                break
            attempt += 1
            if attempt >= MAX_RETRIES:
                break
            await _backoff_sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])

        if verdict.verdict == "error":
            # 降级：fail-open 放行（可用性优先），否则保持待审（合规优先）
            if settings.MODERATION_FAIL_OPEN:
                logger.error("审核服务故障，FAIL_OPEN 放行 post=%s", post_id)
                post.status = 1
            else:
                logger.error("审核服务故障，保持待审 post=%s", post_id)
            await db.commit()
            return

        if verdict.verdict == "reject":
            post.status = -1  # 封禁
            await db.commit()
            logger.info("审核拒绝 post=%s reason=%s trace=%s", post_id, verdict.reason, verdict.trace_id)
            await create_system_notification(db, post.user_id, "moderation", post_id=post.id)
            return

        if verdict.verdict == "review":
            # 机器不确定 → 保持 0，等管理后台人工过审
            logger.info("审核存疑转人工 post=%s trace=%s", post_id, verdict.trace_id)
            return

        post.status = 1  # 正常展示
        await db.commit()
