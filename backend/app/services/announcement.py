"""公告群发：复用 notifications 表（type=announcement + payload + batch_id）。"""
import uuid
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import AdminActor
from app.models.notification import Notification
from app.models.user import User

# 每批 flush 的条数（避免大表单事务内存峰值）
BULK_BATCH_SIZE = 500
# 单次群发接收者上限（保护）
MAX_RECIPIENTS = 50000


async def create_announcement(
    db: AsyncSession,
    actor: AdminActor,
    *,
    title: str,
    content: str,
    audience: Literal["all", "verified"] = "all",
) -> dict:
    """群发公告：all=全部用户，verified=仅认证用户。

    actor_id 自指（系统通知惯例，前端不显示 actor）。
    返回 {batch_id, recipients}。
    """
    conditions = [User.status == 1]
    if audience == "verified":
        conditions.append(User.is_verified.is_(True))

    recipient_ids = (await db.execute(
        select(User.id).where(*conditions).limit(MAX_RECIPIENTS + 1)
    )).scalars().all()
    if len(recipient_ids) > MAX_RECIPIENTS:
        raise ValueError(f"接收者超过上限 {MAX_RECIPIENTS}")

    batch_id = uuid.uuid4().hex
    payload = {"title": title, "content": content}

    buffer: list[Notification] = []
    for uid in recipient_ids:
        buffer.append(Notification(
            user_id=uid, actor_id=uid,  # 自指：绕过"不通知自己"，前端按 type 渲染
            type="announcement", payload=payload, batch_id=batch_id,
        ))
        if len(buffer) >= BULK_BATCH_SIZE:
            db.add_all(buffer)
            await db.flush()
            buffer = []
    if buffer:
        db.add_all(buffer)
    await db.commit()

    return {"batch_id": batch_id, "recipients": len(recipient_ids)}


async def list_announcements(
    db: AsyncSession, *, page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    """公告历史：按 batch_id 聚合（每批一行），倒序分页。"""
    batch_sq = (
        select(
            Notification.batch_id.label("bid"),
            func.min(Notification.id).label("min_id"),
            func.count().label("recipients"),
            func.min(Notification.created_at).label("created_at"),
        )
        .where(Notification.type == "announcement")
        .group_by(Notification.batch_id)
        .subquery()
    )
    total = await db.scalar(select(func.count()).select_from(batch_sq)) or 0

    stmt = (
        select(
            batch_sq.c.bid,
            batch_sq.c.recipients,
            batch_sq.c.created_at,
            Notification.payload,
        )
        .join(Notification, Notification.id == batch_sq.c.min_id)
        .order_by(batch_sq.c.min_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    items = [{
        "batch_id": bid,
        "title": (payload or {}).get("title", ""),
        "content": (payload or {}).get("content", ""),
        "recipients": recipients,
        "created_at": created_at.isoformat() if created_at else None,
    } for bid, recipients, created_at, payload in rows]
    return items, total
