from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tag import PostTag, Tag


async def list_tags(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Tag).order_by(Tag.id))
    tags = result.scalars().all()
    return [{"id": t.id, "name": t.name} for t in tags]


async def create_tag(db: AsyncSession, name: str) -> Tag | None:
    existing = await db.execute(select(Tag).where(Tag.name == name))
    if existing.scalar_one_or_none():
        return None
    tag = Tag(name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def delete_tag(db: AsyncSession, tag_id: int) -> bool:
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        return False
    await db.execute(delete(PostTag).where(PostTag.tag_id == tag_id))
    await db.delete(tag)
    await db.commit()
    return True
