"""组局业务逻辑：创建 / 列表(筛选+进度) / 报名(幂等+满额) / 退出 / 我的局 / 累计人数。"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.party import Party, PartyMember
from app.models.user import User
from app.services.notification import create_notification

# 组局分类白名单（与前端组局页一致）
CATEGORIES = ["自习", "电影", "聚餐", "拼车", "拼单", "运动", "游戏", "旅行", "其他"]


async def create_party(
    db: AsyncSession, user: User, type: str, category: str, title: str,
    content: str, total: int, meet_time=None, location: str | None = None,
) -> Party:
    p = Party(
        user_id=user.id, type=type, category=category, title=title,
        content=content, total=total, meet_time=meet_time, location=location,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


def _party_dict(p: Party, nickname: str, is_joined: bool = False) -> dict:
    return {
        "id": p.id,
        "type": p.type,
        "category": p.category,
        "title": p.title,
        "content": p.content,
        "total": p.total,
        "joined_count": p.joined_count,
        "status": p.status,
        "meet_time": p.meet_time.isoformat() if p.meet_time else None,
        "location": p.location,
        "user": {"nickname": nickname},
        "is_joined": is_joined,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


async def list_parties(
    db: AsyncSession, category: str | None = None, only_vacant: bool = False,
    cursor: int | None = None, limit: int = 20, viewer: User | None = None,
) -> tuple[list[dict], int | None, bool]:
    conds = [Party.status >= 1]  # 1 招募中 / 2 已满，不显示已关闭
    if category:
        conds.append(Party.category == category)
    if only_vacant:
        conds.append(Party.joined_count < Party.total)
    if cursor:
        conds.append(Party.id < cursor)
    stmt = (
        select(Party, User.nickname)
        .join(User, Party.user_id == User.id)
        .where(*conds)
        .order_by(Party.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    joined_ids: set[int] = set()
    if viewer and rows:
        ids = [p.id for p, _ in rows]
        joined_ids = set((await db.execute(
            select(PartyMember.party_id).where(PartyMember.user_id == viewer.id, PartyMember.party_id.in_(ids))
        )).scalars())

    items = [_party_dict(p, nick, is_joined=(p.id in joined_ids)) for p, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def join_party(db: AsyncSession, user: User, party_id: int) -> dict | None:
    # 行锁：并发抢最后名额时串行化 check-then-increment，防超卖
    p = (await db.execute(
        select(Party).where(Party.id == party_id).with_for_update()
    )).scalar_one_or_none()
    if not p:
        return None
    existing = (await db.execute(
        select(PartyMember).where(PartyMember.party_id == party_id, PartyMember.user_id == user.id)
    )).scalar_one_or_none()
    if existing:
        return {"joined": True, "joined_count": p.joined_count}  # 幂等
    if p.status == 2 or (p.joined_count or 0) >= p.total:
        return {"joined": False, "joined_count": p.joined_count, "full": True}  # 已满
    db.add(PartyMember(party_id=party_id, user_id=user.id))
    p.joined_count = (p.joined_count or 0) + 1
    if p.joined_count >= p.total:
        p.status = 2  # 满额自动关闭
    await db.commit()
    await db.refresh(p)
    # 通知发起人（不通知自己）
    await create_notification(db, p.user_id, user.id, "group")
    return {"joined": True, "joined_count": p.joined_count}


async def leave_party(db: AsyncSession, user: User, party_id: int) -> dict | None:
    p = (await db.execute(select(Party).where(Party.id == party_id))).scalar_one_or_none()
    if not p:
        return None
    m = (await db.execute(
        select(PartyMember).where(PartyMember.party_id == party_id, PartyMember.user_id == user.id)
    )).scalar_one_or_none()
    if m:
        await db.delete(m)
        if p.joined_count and p.joined_count > 0:
            p.joined_count -= 1
        if p.status == 2:
            p.status = 1  # 退出后重新开放
        await db.commit()
    await db.refresh(p)
    return {"joined": False, "joined_count": p.joined_count}


async def my_parties(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    conds = [PartyMember.user_id == user.id]
    if cursor:
        conds.append(Party.id < cursor)
    stmt = (
        select(Party, User.nickname)
        .join(PartyMember, PartyMember.party_id == Party.id)
        .join(User, Party.user_id == User.id)
        .where(*conds)
        .order_by(Party.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_party_dict(p, nick, is_joined=True) for p, nick in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def total_members(db: AsyncSession) -> int:
    n = await db.scalar(select(func.count()).select_from(PartyMember))
    return n or 0
