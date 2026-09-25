"""Banner（首页轮播广告位）服务层。"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.banner import Banner

# 首页轮播最多下发的条数（运营位有限，防止误配撑爆轮播）
PUBLIC_BANNER_LIMIT = 10


def _banner_to_dict(b: Banner) -> dict:
    """公开视角：只含投放字段，不含任何管理信息。"""
    return {
        "id": b.id,
        "title": b.title,
        "desc": b.desc,
        "tag": b.tag,
        "image_url": b.image_url,
        "link_url": b.link_url,
        "post_id": b.post_id,
        "activity_id": b.activity_id,
    }


def _banner_to_admin_dict(b: Banner) -> dict:
    """admin 视角：公开字段 + 投放管理字段。"""
    d = _banner_to_dict(b)
    d.update({
        "sort": b.sort,
        "status": b.status,
        "start_at": b.start_at,
        "end_at": b.end_at,
        "created_at": b.created_at,
    })
    return d


async def list_active_banners(db: AsyncSession, limit: int = PUBLIC_BANNER_LIMIT) -> list[dict]:
    """投放中的 banner：status=1 且当前时间落在投放窗口内（含边界），sort 越大越前。"""
    now = datetime.now(timezone.utc)
    stmt = (
        select(Banner)
        .where(
            Banner.status == 1,
            (Banner.start_at.is_(None)) | (Banner.start_at <= now),
            (Banner.end_at.is_(None)) | (Banner.end_at >= now),
        )
        .order_by(Banner.sort.desc(), Banner.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_banner_to_dict(b) for b in rows]


async def list_banners_admin(
    db: AsyncSession, status: int | None = None, cursor: int | None = None, limit: int = 20,
) -> tuple[list[dict], int | None, bool]:
    """admin 列表：全量（含下架），游标分页。"""
    conditions = []
    if status is not None:
        conditions.append(Banner.status == status)
    if cursor:
        conditions.append(Banner.id < cursor)

    stmt = (
        select(Banner)
        .where(*conditions)
        .order_by(Banner.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].id if has_more and rows else None
    return [_banner_to_admin_dict(b) for b in rows], next_cursor, has_more


async def get_banner(db: AsyncSession, banner_id: int) -> Banner | None:
    return (await db.execute(select(Banner).where(Banner.id == banner_id))).scalar_one_or_none()


async def create_banner(db: AsyncSession, data: dict) -> Banner:
    banner = Banner(**data)
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return banner


async def update_banner(db: AsyncSession, banner: Banner, data: dict) -> Banner:
    """部分更新；link_url 有值时清空 post_id（反之亦然），保证跳转目标唯一。"""
    for field, value in data.items():
        setattr(banner, field, value)
    # 三个跳转目标互斥：设置其中一个时清空另外两个
    if data.get("link_url"):
        banner.post_id = None
        banner.activity_id = None
    elif data.get("post_id"):
        banner.link_url = None
        banner.activity_id = None
    elif data.get("activity_id"):
        banner.link_url = None
        banner.post_id = None
    await db.commit()
    await db.refresh(banner)
    return banner


async def delete_banner(db: AsyncSession, banner: Banner) -> None:
    await db.delete(banner)
    await db.commit()
