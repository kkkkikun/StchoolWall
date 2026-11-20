from sqlalchemy import select, func, and_, update, text, literal, tuple_
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload, aliased

from app.models.interaction import Favorite, Footprint, Like
from app.models.post import Post
from app.models.report import Report
from app.models.tag import PostTag
from app.models.user import User
from app.utils.query import escape_like
from app.services.jobs import enqueue_job
from app.services.blocks import visible_author
from app.services.media import bind_media, media_url
from app.services.runtime_controls import moderation_enabled, sensitive_words_enabled

# 微号披露允许的帖型：交易/拼车联系刚需，其余帖型不向其他学生返回 contact_wechat
TRADE_POST_TYPES = {"second_hand", "carpool"}


def _hot_score(p: Post) -> any:
    """推荐热度分：互动加权 / 时间衰减（Reddit 式）。

    - 分子 +1 保底：零互动新帖不被永久淹没，无互动时退化为近似时间序
    - 分母 (发布小时 + 2)^1.2：好帖大约存活 1~2 天后自然沉底
    - 权重与热帖榜（hot_posts）同源：like*3 + comment*2 + view*0.2
    """
    hours = func.extract("epoch", func.now() - p.created_at) / 3600.0
    engagement = p.like_count * 3 + p.comment_count * 2 + p.view_count * 0.2 + 1
    return engagement / func.power(hours + 2, 1.2)


async def create_post(
    db: AsyncSession, user: User, post_type: str, content: str,
    images: list[str], price: float | None, tag_ids: list[int],
    category: str | None = None,
    media_ids: list[uuid.UUID] | None = None,
) -> Post:
    is_admin = user.role == "admin"
    review_enabled = await moderation_enabled()
    if not is_admin and not review_enabled and await sensitive_words_enabled():
        from app.services.sensitive_word import load_active_words
        from app.utils.local_rules import check_text_local
        local, _ = check_text_local(content, await load_active_words(db))
        if local.verdict == "reject":
            raise ValueError("帖子包含违规内容，无法发布")
    status = 1 if is_admin or not review_enabled else 0

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

    assets = await bind_media(db, user.id, media_ids or [], "posts", "post", post.id)
    if assets:
        post.images = [media_url(asset) for asset in assets if asset.status == "approved"]
    if post.status == 0:
        await enqueue_job(db, "moderate_post", {"post_id": post.id}, f"post:{post.id}")
    elif assets:
        from app.services.media import publish_entity_media
        post.images = await publish_entity_media(db, "post", post.id)

    for tid in set(tag_ids):
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
    order: str | None = None,
    tag_id: int | None = None,
    tag_text: str | None = None,
) -> tuple[list[dict], int | None, bool]:
    # 广告轮播由独立 Banner 表承接（GET /banners），广告帖不再混入 feed
    # 置顶：仅"推荐位"（无 category/post_type/order=time）第一页前置置顶块
    # order="time"：最新流，纯 id 倒序（与热度推荐的"精选"并列的两个主 Tab）
    is_recommend = not category and not post_type and order != "time"

    pinned_rows: list = []
    if is_recommend and not cursor:
        pinned_stmt = (
            select(Post, User)
            .join(User, Post.user_id == User.id)
            .where(
                Post.post_type != "advertisement",
                visible_author(Post.user_id, viewer),
                Post.status == 1,
                Post.is_pinned.is_(True),
            )
            .order_by(Post.pinned_at.desc(), Post.id.desc())
        )
        pinned_rows = (await db.execute(pinned_stmt)).all()

    # 普通帖子：游标分页
    conditions = [Post.post_type != "advertisement", Post.status == 1, visible_author(Post.user_id, viewer)]
    # 推荐位置顶帖从主流排除（只在置顶块出现，防止翻页重复）
    if is_recommend:
        conditions.append(Post.is_pinned.is_(False))
    if post_type:
        conditions.append(Post.post_type == post_type)
    if category:
        conditions.append(Post.category == category)
    if tag_id:
        conditions.append(Post.id.in_(select(PostTag.post_id).where(PostTag.tag_id == tag_id)))
    if tag_text:
        conditions.append(Post.content.ilike(f"%#{escape_like(tag_text)}%"))

    if is_recommend:
        # 推荐位：热度分排序 + (score, id) 键集分页（游标仍是上一页末条 id，
        # 其得分在查询时按当前时间重算，对客户端透明）
        score = _hot_score(Post)
        if cursor:
            cur = aliased(Post)
            cur_score = select(_hot_score(cur)).where(cur.id == cursor).scalar_subquery()
            conditions.append(tuple_(score, Post.id) < tuple_(cur_score, literal(cursor)))
        order_clause = (score.desc(), Post.id.desc())
    else:
        # 分类/类型流/最新流：保持最新在前
        if cursor:
            conditions.append(Post.id < cursor)
        order_clause = (Post.id.desc(),)

    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(*conditions)
        .order_by(*order_clause)
        .limit(limit + 1)
    )
    result = await db.execute(stmt)
    rows = result.all()

    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [_post_to_dict(p, u) for p, u in pinned_rows + rows]
    # 行是 (Post, nickname) 元组，游标取 Post.id
    next_cursor = rows[-1][0].id if has_more and rows else None

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

    return items, next_cursor, has_more


async def my_posts(
    db: AsyncSession, user: User, status: int | None = None,
) -> list[dict]:
    """我的帖子：含全部状态（待审/正常/封禁/归档），软删除不显示。"""
    conditions = [Post.user_id == user.id, Post.status != -2]
    if status is not None:
        conditions.append(Post.status == status)
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(*conditions)
        .order_by(Post.id.desc())
        .limit(100)
    )
    rows = (await db.execute(stmt)).all()
    return [_post_to_dict(p, u) for p, u in rows]


async def get_post_detail(
    db: AsyncSession, post_id: int, viewer: User | None
) -> dict | None:
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(Post.id == post_id, visible_author(Post.user_id, viewer))
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        return None

    post, author = row

    # 可见性门禁：仅 status==1 公开；作者本人与 admin 可查看自己的待审/被封/已删帖。
    # 返回 None（404）而非 403，避免对隐藏帖做存在性探测。
    is_privileged = viewer is not None and (
        str(viewer.id) == str(post.user_id) or viewer.role == "admin"
    )
    if post.status != 1 and not is_privileged:
        return None

    # 认证用户：浏览数 +1 并记录足迹（游客不计）
    if viewer:
        await db.execute(
            update(Post).where(Post.id == post_id).values(view_count=Post.view_count + 1)
        )
        await db.execute(
            pg_insert(Footprint).values(user_id=viewer.id, post_id=post_id)
            .on_conflict_do_update(constraint="uq_footprints_user_post", set_={"viewed_at": func.now()})
        )
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
        "is_pinned": bool(post.is_pinned),
        "is_featured": bool(post.is_featured),
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "user_id": str(author.id),
        "user": {"nickname": author.nickname, "avatar_url": author.avatar_url},
        "contact_wechat": None,
        "is_following": False,
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "view_count": post.view_count or 0,
    }

    # 当前用户是否关注了作者
    if viewer and str(author.id) != str(viewer.id):
        from app.services.follow import is_following
        data["is_following"] = await is_following(db, viewer.id, author.id)

    if viewer:
        # 微信号披露范围：admin 全量；作者本人自查；其他认证学生仅交易类帖型（联系刚需）
        is_trade = post.post_type in TRADE_POST_TYPES
        if viewer.role == "admin":
            data["user"]["real_name"] = author.real_name
            data["user"]["student_id"] = author.student_id
            data["contact_wechat"] = author.wechat_id
        elif str(author.id) == str(viewer.id):
            data["user"]["real_name"] = author.real_name
            data["contact_wechat"] = author.wechat_id
        elif viewer.role == "student" and is_trade:
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


async def set_post_pinned(db: AsyncSession, post_id: int, pinned: bool) -> Post | None:
    """管理员置顶/取消置顶；仅对正常展示的帖子有效。"""
    result = await db.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one_or_none()
    if not post or post.status != 1:
        return None

    post.is_pinned = pinned
    post.pinned_at = func.now() if pinned else None
    await db.commit()
    await db.refresh(post)
    return post


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
    if new_status in (-1, -2):
        from app.services.media import reject_entity_media
        await reject_entity_media(db, "post", post_id)
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


def _post_to_dict(post: Post, author: User) -> dict:
    return {
        "id": post.id,
        "post_type": post.post_type,
        "category": post.category,
        "content": post.content,
        "images": post.images,
        "price": float(post.price) if post.price else None,
        "status": post.status,
        "is_pinned": bool(post.is_pinned),
        "is_featured": bool(post.is_featured),
        "user": {"nickname": author.nickname, "avatar_url": author.avatar_url},
        "like_count": post.like_count or 0,
        "comment_count": post.comment_count or 0,
        "view_count": post.view_count or 0,
        "is_liked": False,
        "is_favorited": False,
        "created_at": post.created_at.isoformat() if post.created_at else None,
    }


async def hot_posts(db: AsyncSession, limit: int = 10, viewer: User | None = None) -> list[dict]:
    """十大热帖：近 7 天、正常、非广告，按 like*3 + comment*2 + view 加权倒序。"""
    score = Post.like_count * 3 + Post.comment_count * 2 + Post.view_count
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(
            Post.status == 1,
            visible_author(Post.user_id, viewer),
            Post.post_type != "advertisement",
            # 热帖门槛：零互动新帖不进榜（否则 tie-break 让新帖冒充热帖）
            (Post.like_count * 3 + Post.comment_count * 2 + Post.view_count) > 0,
            Post.created_at >= func.now() - text("interval '7 days'"),
        )
        .order_by(score.desc(), Post.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [_post_to_dict(p, u) for p, u in rows]


async def featured_posts(
    db: AsyncSession, cursor: int | None = None, limit: int = 20, tag_text: str | None = None,
    viewer: User | None = None,
) -> tuple[list[dict], int | None, bool]:
    """精华流：经验贴等长尾内容，按历史总热度排序（无时间衰减），键集分页。"""
    score = Post.like_count * 3 + Post.comment_count * 2 + Post.view_count
    conds = [Post.is_featured.is_(True), Post.status == 1, Post.post_type != "advertisement", visible_author(Post.user_id, viewer)]
    if tag_text:
        conds.append(Post.content.ilike(f"%#{escape_like(tag_text)}%"))
    if cursor:
        cur = aliased(Post)
        cur_score = select(
            cur.like_count * 3 + cur.comment_count * 2 + cur.view_count
        ).where(cur.id == cursor).scalar_subquery()
        conds.append(tuple_(score, Post.id) < tuple_(cur_score, literal(cursor)))
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(score.desc(), Post.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_post_to_dict(p, u) for p, u in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def feature_candidates(db: AsyncSession, limit: int = 20) -> list[dict]:
    """精华候选：未设精的正常帖里互动最高的（运营一键采纳）。"""
    score = Post.like_count * 3 + Post.comment_count * 2 + Post.view_count
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(
            Post.is_featured.is_(False),
            Post.status == 1,
            Post.post_type != "advertisement",
            score >= 10,  # 互动门槛：过滤零互动噪音
        )
        .order_by(score.desc(), Post.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [_post_to_dict(p, u) for p, u in rows]


async def set_post_featured(db: AsyncSession, post_id: int, featured: bool) -> Post | None:
    """设/取消精华。幂等：重复设置不覆盖 featured_at 首次时间。"""
    post = (await db.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if not post:
        return None
    if featured and not post.is_featured:
        post.is_featured = True
        post.featured_at = func.now()
    elif not featured and post.is_featured:
        post.is_featured = False
        post.featured_at = None
    await db.commit()
    await db.refresh(post)
    return post


async def search_posts(
    db: AsyncSession, q: str, cursor: int | None = None, limit: int = 20, viewer: User | None = None
) -> tuple[list[dict], int | None, bool]:
    """全文搜索（PostgreSQL ILIKE），仅正常非广告帖；精华帖置顶（键集分页）。"""
    conds = [Post.status == 1, Post.post_type != "advertisement", Post.content.ilike(f"%{escape_like(q)}%"), visible_author(Post.user_id, viewer)]
    if cursor:
        # 精华置顶后的键集翻页：游标行的 (is_featured, id) 之后再取
        cur = aliased(Post)
        cur_featured = select(cur.is_featured).where(cur.id == cursor).scalar_subquery()
        conds.append(tuple_(Post.is_featured, Post.id) < tuple_(cur_featured, literal(cursor)))
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Post.is_featured.desc(), Post.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [_post_to_dict(p, u) for p, u in rows]
    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def following_feed(
    db: AsyncSession, user: User, cursor: int | None = None, limit: int = 20, tag_text: str | None = None
) -> tuple[list[dict], int | None, bool]:
    """关注流：已关注用户的正常非广告帖，按时间倒序。"""
    from app.models.follow import UserFollow

    followed = select(UserFollow.followee_id).where(UserFollow.follower_id == user.id)
    conds = [Post.status == 1, Post.post_type != "advertisement", Post.user_id.in_(followed), visible_author(Post.user_id, user)]
    if tag_text:
        conds.append(Post.content.ilike(f"%#{escape_like(tag_text)}%"))
    if cursor:
        conds.append(Post.id < cursor)
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Post.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [_post_to_dict(p, u) for p, u in rows]
    if items:
        ids = [it["id"] for it in items]
        liked_ids = set((await db.execute(
            select(Like.post_id).where(Like.user_id == user.id, Like.post_id.in_(ids))
        )).scalars())
        fav_ids = set((await db.execute(
            select(Favorite.post_id).where(Favorite.user_id == user.id, Favorite.post_id.in_(ids))
        )).scalars())
        for it in items:
            it["is_liked"] = it["id"] in liked_ids
            it["is_favorited"] = it["id"] in fav_ids

    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more


async def user_posts(
    db: AsyncSession, user_id: uuid.UUID, viewer: User | None = None,
    cursor: int | None = None, limit: int = 20,
) -> tuple[list[dict], int | None, bool]:
    """某用户公开主页的帖子（status=1、非广告），带查看者互动视角。"""
    conds = [Post.user_id == user_id, Post.status == 1, Post.post_type != "advertisement", visible_author(Post.user_id, viewer)]
    if cursor:
        conds.append(Post.id < cursor)
    stmt = (
        select(Post, User)
        .join(User, Post.user_id == User.id)
        .where(*conds)
        .order_by(Post.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [_post_to_dict(p, u) for p, u in rows]
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

    next_cursor = rows[-1][0].id if has_more and rows else None
    return items, next_cursor, has_more
