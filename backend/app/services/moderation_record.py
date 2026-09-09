"""机器审核记录：写入（add-only）+ 管理端查询。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.moderation_record import ModerationRecord
from app.utils.moderation import ModerationResult


def add_moderation_record(
    db: AsyncSession,
    post_id: int,
    source: str,
    result: ModerationResult,
    matched: list[str] | None = None,
    comment_id: int | None = None,
) -> ModerationRecord:
    """只 add 不 commit，随调用方事务落库（同 log_admin_action 约定）。

    帖审核：post_id=被审帖；评论审核：post_id=被评帖 + comment_id=被审评论
    （评论被硬词直接拒时评论未创建，comment_id 为空）。
    """
    record = ModerationRecord(
        post_id=post_id,
        comment_id=comment_id,
        source=source,
        verdict=result.verdict,
        matched=matched,
        reason=result.reason,
        trace_id=result.trace_id,
    )
    db.add(record)
    return record


async def list_moderation_records(
    db: AsyncSession,
    *,
    verdict: str | None = None,
    source: str | None = None,
    post_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ModerationRecord], int]:
    """管理端查询：verdict/source/post_id 筛选 + 分页，id 倒序。只读。"""
    conditions = []
    if verdict:
        conditions.append(ModerationRecord.verdict == verdict)
    if source:
        conditions.append(ModerationRecord.source == source)
    if post_id:
        conditions.append(ModerationRecord.post_id == post_id)
    base = select(ModerationRecord).where(*conditions)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(ModerationRecord.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(items), total
