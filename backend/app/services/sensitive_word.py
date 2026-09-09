"""敏感词库服务：审核用加载器 + 管理端 CRUD。"""
from sqlalchemy import func, select
from app.utils.query import escape_like
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensitive_word import SensitiveWord


async def load_active_words(db: AsyncSession) -> list[tuple[str, str]]:
    """全量读取词库（词在匹配时归一化）。低 QPS 下每次审核读库即天然热加载。"""
    rows = (await db.execute(select(SensitiveWord))).scalars().all()
    return [(r.word, r.level) for r in rows]


async def get_sensitive_word(db: AsyncSession, word_id: int) -> SensitiveWord | None:
    return (await db.execute(select(SensitiveWord).where(SensitiveWord.id == word_id))).scalar_one_or_none()


async def list_sensitive_words(
    db: AsyncSession,
    *,
    q: str | None = None,
    level: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SensitiveWord], int]:
    """管理端列表：词/级别筛选 + 分页，id 倒序。"""
    conditions = []
    if q:
        conditions.append(SensitiveWord.word.ilike(f"%{escape_like(q)}%"))
    if level:
        conditions.append(SensitiveWord.level == level)
    base = select(SensitiveWord).where(*conditions)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (await db.execute(
        base.order_by(SensitiveWord.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return list(items), total


async def create_sensitive_word(
    db: AsyncSession, word: str, level: str, created_by: str | None = None
) -> SensitiveWord:
    exists = (await db.execute(select(SensitiveWord).where(SensitiveWord.word == word))).scalar_one_or_none()
    if exists:
        raise ValueError("该敏感词已存在")
    item = SensitiveWord(word=word, level=level, created_by=created_by)
    db.add(item)
    await db.flush()
    return item


async def update_sensitive_word(db: AsyncSession, item: SensitiveWord, *, word: str, level: str) -> SensitiveWord:
    dup = (await db.execute(
        select(SensitiveWord).where(SensitiveWord.word == word, SensitiveWord.id != item.id)
    )).scalar_one_or_none()
    if dup:
        raise ValueError("该敏感词已存在")
    item.word = word
    item.level = level
    await db.flush()
    return item


async def delete_sensitive_word(db: AsyncSession, item: SensitiveWord) -> None:
    await db.delete(item)
    await db.flush()
