"""管理后台评论管理：列表 + 软删。"""
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Comment
from app.models.post import Post
from app.models.user import User


async def list_comments_admin(
    db: AsyncSession,
    *,
    q: str | None = None,
    post_id: int | None = None,
    status: int | None = None,
    time_start=None,
    time_end=None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    conditions = []
    if q:
        conditions.append(Comment.content.ilike(f"%{q}%"))
    if post_id is not None:
        conditions.append(Comment.post_id == post_id)
    if status is not None:
        conditions.append(Comment.status == status)
    if time_start:
        conditions.append(Comment.created_at >= time_start)
    if time_end:
        conditions.append(Comment.created_at <= time_end)

    total = await db.scalar(
        select(func.count()).select_from(Comment).where(*conditions)
    ) or 0

    stmt = (
        select(Comment, User.nickname, Post.content)
        .join(User, Comment.user_id == User.id)
        .join(Post, Comment.post_id == Post.id)
        .where(*conditions)
        .order_by(Comment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    items = [{
        "id": c.id,
        "post_id": c.post_id,
        "post_content": pc[:50],
        "author": {"nickname": nick, "id": str(c.user_id)},
        "content": c.content,
        "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    } for c, nick, pc in rows]
    return items, total


async def admin_delete_comment(db: AsyncSession, comment_id: int) -> bool | None:
    """软删评论并同步维护帖子评论计数；不存在返回 None，重复删返回 False。"""
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    comment = result.scalar_one_or_none()
    if not comment:
        return None
    if comment.status == -1:
        return False  # 已删除（幂等）

    comment.status = -1
    # 维护冗余计数
    await db.execute(
        update(Post).where(Post.id == comment.post_id)
        .values(comment_count=func.greatest(Post.comment_count - 1, 0))
    )
    await db.commit()
    return True
