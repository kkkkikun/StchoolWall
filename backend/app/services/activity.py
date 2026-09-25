"""站内活动/专题页服务：公开详情 / 管理 CRUD。"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity


def _to_dict(a: Activity) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "image_url": a.image_url,
        "summary": a.summary,
        "content": a.content,
        "location": a.location,
        "start_at": a.start_at.isoformat() if a.start_at else None,
        "end_at": a.end_at.isoformat() if a.end_at else None,
        "status": a.status,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


async def get_public_activity(db: AsyncSession, activity_id: int) -> dict | None:
    """公开详情：只返回上架活动。"""
    a = (await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.status == 1)
    )).scalar_one_or_none()
    return _to_dict(a) if a else None


async def list_admin_activities(
    db: AsyncSession, *, q: str | None = None, status: int | None = None,
    page: int = 1, page_size: int = 20,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(Activity.title.ilike(f"%{q}%"))
    if status is not None:
        conditions.append(Activity.status == status)

    total = await db.scalar(
        select(func.count()).select_from(Activity).where(*conditions)
    ) or 0
    rows = (await db.execute(
        select(Activity).where(*conditions)
        .order_by(Activity.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return [_to_dict(a) for a in rows], total


async def get_activity(db: AsyncSession, activity_id: int) -> Activity | None:
    return (await db.execute(select(Activity).where(Activity.id == activity_id))).scalar_one_or_none()


async def create_activity(db: AsyncSession, data: dict) -> Activity:
    a = Activity(**data)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


async def update_activity(db: AsyncSession, a: Activity, data: dict) -> Activity:
    for field, value in data.items():
        setattr(a, field, value)
    await db.commit()
    await db.refresh(a)
    return a


async def delete_activity(db: AsyncSession, a: Activity) -> None:
    await db.delete(a)
    await db.commit()
