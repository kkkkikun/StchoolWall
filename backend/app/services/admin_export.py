"""CSV 导出：流式生成（每批 500 行），users 导出强制审计。"""
import csv
import io
from collections.abc import AsyncGenerator

from sqlalchemy import select
from app.utils.query import escape_like
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import AdminActor
from app.models.post import Post
from app.models.user import User
from app.services import admin_log
from app.services.admin_log import log_admin_action

EXPORT_BATCH = 500

# UTF-8 BOM：Excel 直接打开中文不乱码
BOM = "﻿"


def _csv_chunk(rows: list[list]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows([[_csv_safe_cell(c) for c in row] for row in rows])
    return buf.getvalue()


def _csv_safe_cell(value) -> str:
    """CSV 公式注入防护：= + - @ 开头的单元格加 ' 前缀（Excel/WPS 打开导出文件时防执行）。"""
    s = str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s


async def iter_posts_csv(
    db: AsyncSession, *, status: int | None = None, q: str | None = None
) -> AsyncGenerator[str, None]:
    """帖子 CSV 流：id/类型/分类/内容/状态/作者昵称/互动计数/时间。"""
    yield BOM + _csv_chunk([[
        "id", "post_type", "category", "content", "status", "is_pinned",
        "author_nickname", "like_count", "comment_count", "view_count", "created_at",
    ]])

    conditions = []
    if status is not None:
        conditions.append(Post.status == status)
    if q:
        from sqlalchemy import or_
        conditions.append(or_(Post.content.ilike(f"%{escape_like(q)}%")))

    last_id = 0
    while True:
        conds = [*conditions, Post.id > last_id]
        stmt = (
            select(Post, User.nickname)
            .join(User, Post.user_id == User.id)
            .where(*conds)
            .order_by(Post.id.asc())
            .limit(EXPORT_BATCH)
        )
        rows = (await db.execute(stmt)).all()
        if not rows:
            break
        chunk = [[
            p.id, p.post_type, p.category or "", p.content.replace("\n", " "),
            p.status, p.is_pinned, nick, p.like_count, p.comment_count, p.view_count,
            p.created_at.isoformat() if p.created_at else "",
        ] for p, nick in rows]
        yield _csv_chunk(chunk)
        last_id = rows[-1][0].id
        if len(rows) < EXPORT_BATCH:
            break


async def iter_users_csv(
    db: AsyncSession, actor: AdminActor, *, ip: str | None = None
) -> AsyncGenerator[str, None]:
    """用户 CSV 流（含 real_name/student_id 敏感字段——导出前强制审计）。"""
    # 强制审计：敏感数据离开系统必须留痕
    await log_admin_action(db, actor, admin_log.EXPORT_USERS, target_type="user",
                           detail={"fields": ["nickname", "real_name", "student_id", "role", "status"]},
                           ip=ip)
    await db.commit()

    yield BOM + _csv_chunk([[
        "id", "nickname", "real_name", "student_id", "role",
        "is_verified", "status", "created_at",
    ]])

    last_id = None
    while True:
        conds = []
        if last_id is not None:
            conds.append(User.id > last_id)
        stmt = (
            select(User)
            .where(*conds)
            .order_by(User.id.asc())
            .limit(EXPORT_BATCH)
        )
        rows = (await db.execute(stmt)).scalars().all()
        if not rows:
            break
        chunk = [[
            str(u.id), u.nickname, u.real_name or "", u.student_id or "", u.role,
            u.is_verified, u.status,
            u.created_at.isoformat() if u.created_at else "",
        ] for u in rows]
        yield _csv_chunk(chunk)
        last_id = rows[-1].id
        if len(rows) < EXPORT_BATCH:
            break
