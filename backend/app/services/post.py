from sqlalchemy import select, func, and_, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interaction import Favorite, Footprint, Like
from app.models.post import Post
from app.models.report import Report
from app.models.tag import PostTag
from app.models.user import User


async def create_post(
    db: AsyncSession, user: User, post_type: str, content: str,
    images: list[str], price: float | None, tag_ids: list[int],
    category: str | None = None,
) -> Post:
    is_admin = user.role == "admin"
    status = 1 if is_admin else 0  # admin 直接通过审核

    post = Post(
        user_id=user.id,
        post_type=post_type,
        category=category,
        content=content,
        images=images,
        price=price,
        status=status,
    )
    db.add(post)
    await db.flush()

    for tid in tag_ids:
        db.add(PostTag(post_id=post.id, tag_id=tid))

    await db.commit()
    await db.refresh(post)
    return post


async def list_posts(
    db: AsyncSession,
    cursor: int | None = None,
    post_type: str | None = None,
    limit: int = 20,
    viewer: User | None = None,
    category: str | None = None,
) -> tuple[list[dict], int | None, bool]:
    # 分类筛选时不置顶广告（按分类看时广告无关）
    ad_rows = []
    if not category:
        ad_stmt = (
            select(Post, User.nickname)
            .join(User, Post.user_id == User.id)
            .where(Post.post_type == "advertisement", Post.status == 1)
            .order_by(Post.created_at.desc())
        )
        ad_rows = (await db.execute(ad_stmt)).all()

    # 普通帖子：游标分页
    conditions = [Post.post_type != "advertisement", Post.status == 1]
    if cursor:
        conditions.append(Post.id < cursor)
    if post_type:
        conditions.append(Post.post_type == post_type)
    if category:
        conditions.append(Post.category == category)

    stmt = (
        select(Post, User.nickname)
        .join(User, Post.user_id == User.id)
        .where(*conditions)
        .order_by(Post.created_at.desc())
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [_post_to_dict(p, nick) for p, nick in ad_rows + rows]

    # 当前用户的点赞/收藏视角（批量查询）
    if viewer and items:
        ids = [it["id"] for it in items]
        liked_ids = set((await db.execute(
            select(Like.post_id).where(Like.user_id == viewer.id, Like.post_id.in_(ids))
        )).scalars())
        fav_ids = set((await db.execute(
            select(Favorite.post_id).where(Favorite.user_id == viewer.id, Favorite.post_id.in_(ids))
        )).scalars())
        for it in items:
            it["is_liked"] = it["id"] in liked_ids
            it["is_favorited"] = it["id"] in fav_ids

    next_cursor = rows[-1].id if has_more and rows else None

    return items, next_cursor, has_more


async def get_post_detail(
    db: AsyncSession, post_id: int, viewer: User | None
) -> dict | None:
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(Post.id == post_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None

    post, author = row

    # 认证用户：浏览数 +1 并记录足迹（游客不计）
    if viewer:
        await db.execute(
            update(Post).where(Post.id == post_id).values(view_count=Post.view_count + 1)
        )
        fp = (await db.execute(
            select(Footprint).where(Footprint.user_id == viewer.id, Footprint.post_id == post_id)
        )).scalar_one_or_none()
        if fp:
            await db.execute(update(Footprint).where(Footprint.id == fp.id).values(viewed_at=func.now()))
        else:
            db.add(Footprint(user_id=viewer.id, post_id=post_id))
        await db.commit()
        await db.refresh(post)

    # 隐私隔离逻辑
    data = {
        "id": post.id,
        "post_type": post.post_type,
        "category": post.category,
        "content": post.content,
        "images": post.images,
        "price": float(post.price) if post.price else None,
        "status": post.status,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "user": {"nickname": author.nickname},
        "contact_wechat": None,
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "view_count": post.view_count or 0,
    }

    if viewer:
        if viewer.role == "admin":
            data["user"]["real_name"] = author.real_name
            data["user"]["student_id"] = author.student_id
            data["contact_wechat"] = author.wechat_id
        elif str(author.id) == str(viewer.id):
            data["user"]["real_name"] = author.real_name
        elif viewer.role == "student":
            data["contact_wechat"] = author.wechat_id
        # 当前用户的互动视角
        liked = (await db.execute(
            select(Like).where(Like.user_id == viewer.id, Like.post_id == post_id)
        )).scalar_one_or_none()
        fav = (await db.execute(
            select(Favorite).where(Favorite.user_id == viewer.id, Favorite.post_id == post_id)
        )).scalar_one_or_none()
        data["is_liked"] = liked is not None
        data["is_favorited"] = fav is not None
    else:
        data["is_liked"] = False
        data["is_favorited"] = False
    # guest: contact_wechat stays None, no real_name

    return data


async def update_post_status(
    db: AsyncSession, post_id: int, user: User, new_status: int
) -> Post | None:
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        return None

    # 只有作者本人可以归档/删除自己的帖子
    if str(post.user_id) != str(user.id) and user.role != "admin":
        return None

    # 状态流转校验
    valid = False
    if new_status == 2 and post.status == 1:
        valid = True  # 标记已解决
    elif new_status == -2 and post.status in (1, 2):
        valid = True  # 软删除
    elif new_status == -1 and user.role == "admin" and post.status in (0, 1, 2):
        valid = True  # admin 封禁

    if not valid:
        return None

    post.status = new_status
    await db.commit()
    await db.refresh(post)
    return post


async def report_post(
    db: AsyncSession, post_id: int, reporter: User,
    reason: str, description: str | None,
) -> Report | None:
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        return None

    report = Report(
        post_id=post_id,
        reporter_id=reporter.id,
        reason=reason,
        description=description,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


def _post_to_dict(post: Post, nickname: str) -> dict:
    return {
        "id": post.id,
        "post_type": post.post_type,
        "category": post.category,
        "content": post.content,
        "images": post.images,
        "price": float(post.price) if post.price else None,
        "status": post.status,
        "user": {"nickname": nickname},
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "view_count": post.view_count or 0,
        "is_liked": False,
        "is_favorited": False,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


async def hot_posts(db: AsyncSession, limit: int = 10) -> list[dict]:
    """十大热帖：近 7 天、正常、非广告，按 like*3 + comment*2 + view 加权倒序。"""
    score = Post.like_count * 3 + Post.comment_count * 2 + Post.view_count
    stmt = (
        select(Post, User.nickname)
        .join(User, Post.user_id == User.id)
        .where(
            Post.status == 1,
            Post.post_type != "advertisement",
            Post.created_at >= func.now() - text("interval '7 days'"),
        )
        .order_by(score.desc(), Post.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [_post_to_dict(p, nick) for p, nick in rows]


async def search_posts(
    db: AsyncSession, q: str, cursor: int | None = None, limit: int = 20
) -> tuple[list[dict], int | None, bool]:
    """全文搜索（PostgreSQL ILIKE），仅正常非广告帖。"""
    conds = [Post.status == 1, Post.post_type != "advertisement", Post.content.ilike(f"%{q}%")]
    if cursor:
        conds.append(Post.id < cursor)
    stmt = (
        select(Post, User.nickname)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Post.created_at.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_post_to_dict(p, nick) for p, nick in rows]
    next_cursor = rows[-1].id if has_more and rows else None
    return items, next_cursor, has_more
