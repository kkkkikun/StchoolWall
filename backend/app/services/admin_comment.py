"""管理后台评论管理：列表 + 软删。"""
from sqlalchemy import func, select, update
from app.utils.query import escape_like
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
        conditions.append(Comment.content.ilike(f"%{escape_like(q)}%"))
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
    result = await db.execute(select(Comment).where(Comment.id == comment_id).with_for_update())
    comment = result.scalar_one_or_none()
    if not comment:
        return None
    if comment.status == -1:
        return False  # 已删除（幂等）

    was_public = comment.status == 1
    comment.status = -1
    if was_public:
        await db.execute(
            update(Post).where(Post.id == comment.post_id)
            .values(comment_count=func.greatest(Post.comment_count - 1, 0))
        )
    await db.flush()
    return True


# 评论状态机：待审 → 过审/拒审；正常 → 拒审（等价软删）；已删不可逆
COMMENT_STATUS_TRANSITIONS = {0: {1, -1}, 1: {-1}}


async def admin_update_comment_status(db: AsyncSession, comment_id: int, new_status: int):
    """管理端评论状态流转。返回 (comment, error) 二元组：error 非 None 时前端直接展示。

    - 0→1 过审：补公开计数 +1，并补发帖子作者的评论通知
      （待审期间未计数未通知，语义与"过审才可见"一致）
    - 0→-1 / 1→-1 拒审/下架：计数 -1（若曾在计数中）
    """
    comment = (await db.execute(select(Comment).where(Comment.id == comment_id).with_for_update())).scalar_one_or_none()
    if not comment:
        return None, "评论不存在"
    allowed = COMMENT_STATUS_TRANSITIONS.get(comment.status, set())
    if new_status not in allowed:
        return comment, f"不允许的状态流转（{comment.status} → {new_status}）"

    post = None
    if comment.status == 0 and new_status == 1:
        from app.services.blocks import blocked_between
        post = (await db.execute(select(Post).where(
            Post.id == comment.post_id,
        ).with_for_update())).scalar_one_or_none()
        if post is None or post.status != 1:
            return comment, "帖子当前不可见，无法发布评论"
        if await blocked_between(db, comment.user_id, post.user_id):
            return comment, "存在拉黑关系，无法发布评论"

    old_status = comment.status
    comment.status = new_status

    if old_status == 0 and new_status == 1:
        # 过审：补计数 + 通知帖子作者（不通知评论者自己）
        await db.execute(
            update(Post).where(Post.id == comment.post_id)
            .values(comment_count=Post.comment_count + 1)
        )
        await db.flush()
        from app.services.notification import create_notification
        if str(post.user_id) != str(comment.user_id):
            await create_notification(db, post.user_id, comment.user_id, "comment",
                                      post_id=post.id, comment_id=comment.id, commit=False)
        else:
            await db.flush()
    elif new_status == -1 and old_status == 1:
        await db.execute(
            update(Post).where(Post.id == comment.post_id)
            .values(comment_count=func.greatest(Post.comment_count - 1, 0))
        )
        await db.flush()
    else:
        await db.flush()

    await db.refresh(comment)
    return comment, None
