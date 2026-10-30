"""管理后台组局管理：列表 + 关闭/恢复 + 报名明细。"""
from sqlalchemy import func, select
from app.utils.query import escape_like
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.party import Party, PartyMember
from app.models.user import User

# admin 允许的组局状态流转：招募中/已满 → 关闭；关闭 → 恢复
PARTY_STATUS_TRANSITIONS = {0: {1, -1}, 1: {-1}, 2: {-1}, -1: {1}}


def _party_to_dict(p: Party, nick: str) -> dict:
    return {
        "id": p.id,
        "type": p.type,
        "category": p.category,
        "title": p.title,
        "content": p.content[:80],
        "total": p.total,
        "joined_count": p.joined_count,
        "status": p.status,
        "meet_time": p.meet_time.isoformat() if p.meet_time else None,
        "location": p.location,
        "organizer": {"nickname": nick, "id": str(p.user_id)},
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


async def list_parties_admin(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: int | None = None,
    type: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        like = f"%{escape_like(q)}%"
        conditions.append(Party.title.ilike(like) | Party.content.ilike(like))
    if status is not None:
        conditions.append(Party.status == status)
    if type:
        conditions.append(Party.type == type)
    if category:
        conditions.append(Party.category == category)

    total = await db.scalar(
        select(func.count()).select_from(Party).where(*conditions)
    ) or 0
    stmt = (
        select(Party, User.nickname)
        .join(User, Party.user_id == User.id)
        .where(*conditions)
        .order_by(Party.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    return [_party_to_dict(p, nick) for p, nick in rows], total


async def admin_update_party_status(db: AsyncSession, party_id: int, new_status: int) -> Party | None | str:
    """组局状态流转；非法流转返回 'invalid'，不存在返回 None。"""
    result = await db.execute(select(Party).where(Party.id == party_id).with_for_update())
    party = result.scalar_one_or_none()
    if not party:
        return None
    allowed = PARTY_STATUS_TRANSITIONS.get(party.status, set())
    if new_status not in allowed:
        return "invalid"
    party.status = 2 if new_status == 1 and party.joined_count >= party.total else new_status
    await db.flush()
    await db.refresh(party)
    return party


async def list_party_members_admin(
    db: AsyncSession,
    party_id: int,
    *,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[dict] | None, int]:
    """组局报名明细（仅 admin）。组局不存在返回 (None, 0)。"""
    party = await db.get(Party, party_id)
    if party is None:
        return None, 0

    total = await db.scalar(
        select(func.count()).select_from(PartyMember).where(PartyMember.party_id == party_id)
    ) or 0

    stmt = (
        select(PartyMember, User)
        .join(User, PartyMember.user_id == User.id)
        .where(PartyMember.party_id == party_id)
        .order_by(PartyMember.joined_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    items = [{
        "user_id": str(u.id),
        "nickname": u.nickname,
        "student_id": u.student_id,
        "real_name": u.real_name,
        "joined_at": m.joined_at.isoformat() if m.joined_at else None,
    } for m, u in rows]
    return items, total
