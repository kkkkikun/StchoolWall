"""异步内容审核后台任务

发布学生帖后由 FastAPI BackgroundTasks 调用：
- 仅传序列化参数 (post_id)，不传 ORM 对象（请求已结束）
- 新开 DB session 重查帖子与作者（msg_sec_check v2 需要 openid）
- 三层判定并联取最严：
  - rule：本地敏感词（hard→reject / gray→review）+ 频率风控，永远执行
  - wechat：msg_sec_check/img_sec_check，_is_configured 门禁（未配置即 pass）
- verdict 分流：pass→1 / reject→-1+通知 / review→保持0等人工 / error→重试后降级
- 每次审核按来源落 moderation_records（rule 行恒写；wechat 行仅真实调用时写）

注意（设计约束）：本地/频率判定先于重试循环算一次，循环条件只看微信 verdict——
本地 review 严重度(2) > error(1)，折进循环会提前终止微信重试。
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.post import Post
from app.models.user import User
from app.services.moderation_record import add_moderation_record
from app.services.notification import create_system_notification
from app.services.sensitive_word import load_active_words
from app.utils.local_rules import check_text_local
from app.utils.moderation import (
    ModerationResult,
    _is_configured,
    _strictest,
    check_images,
    check_text,
)

logger = logging.getLogger(__name__)

# 网络故障重试次数与退避（秒）
MAX_RETRIES = 3
BACKOFF_SECONDS = [2, 4]

# 频率风控：滚动窗口内发帖数（含当前帖，任意状态）达到阈值 → 转人工
FREQ_WINDOW_MINUTES = 10
FREQ_MAX_POSTS = 3


async def _backoff_sleep(seconds: float) -> None:
    """退避等待（测试里可 monkeypatch 置零）。"""
    await asyncio.sleep(seconds)


async def _check_frequency(db: AsyncSession, user_id) -> ModerationResult:
    """同一用户短时间高频发帖 → 转人工（灌水/刷屏兜底，DB 计数不依赖 Redis）。"""
    since = datetime.now(timezone.utc) - timedelta(minutes=FREQ_WINDOW_MINUTES)
    count = (await db.execute(
        select(func.count()).select_from(Post).where(Post.user_id == user_id, Post.created_at >= since)
    )).scalar() or 0
    if count >= FREQ_MAX_POSTS:
        return ModerationResult("review", reason=f"高频发帖（{FREQ_WINDOW_MINUTES}分钟内≥{FREQ_MAX_POSTS}条）")
    return ModerationResult("pass")


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

        # ---- rule 层：本地敏感词 + 频率（先算一次，不参与微信重试） ----
        local_r, matched = check_text_local(post.content, await load_active_words(db))
        freq_r = await _check_frequency(db, post.user_id)
        rule_r = _strictest([local_r, freq_r])

        # ---- wechat 层：本地已 reject 时跳过（省配额，reject 已是最严） ----
        skip_wechat = rule_r.verdict == "reject"
        if skip_wechat:
            wechat_r = ModerationResult("pass")
        else:
            attempt = 0
            while True:
                text_r = await check_text(post.content, openid)
                image_r = await check_images(post.images or [])
                wechat_r = _strictest([text_r, image_r])

                if wechat_r.verdict != "error":
                    break
                attempt += 1
                if attempt >= MAX_RETRIES:
                    break
                await _backoff_sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])

        # ---- 审核记录：循环退出后写一次（防重试重复写），随下方各分支 commit 落库 ----
        add_moderation_record(db, post_id, "rule", rule_r, matched=matched or None)
        if not skip_wechat and _is_configured():
            add_moderation_record(db, post_id, "wechat", wechat_r)

        verdict = _strictest([rule_r, wechat_r])

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
            # 机器不确定 → 保持 0，等管理后台人工过审（记录需随本分支 commit 落库）
            logger.info("审核存疑转人工 post=%s trace=%s", post_id, verdict.trace_id)
            await db.commit()
            return

        post.status = 1  # 正常展示
        await db.commit()
