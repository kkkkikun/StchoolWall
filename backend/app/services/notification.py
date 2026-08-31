"""消息通知业务逻辑：创建（被互动动作调用）、列表、未读汇总、标记已读。"""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
    type: str,
    post_id: int | None = None,
    comment_id: int | None = None,
) -> Notification | None:
    """创建通知；不通知自己。"""
    if str(user_id) == str(actor_id):
        return None
    n = Notification(
        user_id=user_id, actor_id=actor_id, type=type,
        post_id=post_id, comment_id=comment_id,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


async def create_system_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    post_id: int | None = None,
) -> Notification:
    """系统通知（审核结果等）：actor_id 自指以落库，前端按 type 渲染系统文案、不显示 actor。"""
    n = Notification(
        user_id=user_id, actor_id=user_id, type=type, post_id=post_id,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return n


def _notif_dict(n: Notification, actor_nick: str) -> dict:
    d = {
        "id": n.id,
        "type": n.type,
        "actor": {"nickname": actor_nick},
        "post_id": n.post_id,
        "comment_id": n.comment_id,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }
    if n.payload:
        d["payload"] = n.payload
    return d


async def list_notifications(
    db: AsyncSession, user: User, type: str | None = None,
    cursor: int | None = None, limit: int = 20,
) -> tuple[list[dict], int | None, bool]:
    conds = [Notification.user_id == user.id]
    if type:
        conds.append(Notification.type == type)
    if cursor:
        conds.append(Notification.id < cursor)
    # 未读在前，再按时间倒序
    stmt = (
        select(Notification, User.nickname)
        .join(User, Notification.actor_id == User.id)
        .where(*conds)
        .order_by(Notification.is_read.asc(), Notification.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_notif_dict(n, nick) for n, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def unread_summary(db: AsyncSession, user: User) -> dict:
    """按消息页 4 类聚合未读数（im 恒 0，私信未实现）。"""
    stmt = (
        select(Notification.type, func.count())
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .group_by(Notification.type)
    )
    rows = (await db.execute(stmt)).all()
    counts = {t: c for t, c in rows}
    return {
        "comment": counts.get("comment", 0),
        "like": counts.get("like", 0),
        "group": counts.get("group", 0),
        "moderation": counts.get("moderation", 0),
        "announcement": counts.get("announcement", 0),
        "im": 0,
    }


async def mark_all_read(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.commit()
    return result.rowcount or 0


async def mark_read(db: AsyncSession, user: User, notif_id: int) -> bool:
    n = (await db.execute(
        select(Notification).where(Notification.id == notif_id, Notification.user_id == user.id)
    )).scalar_one_or_none()
    if not n:
        return False
    n.is_read = True
    await db.commit()
    return True
