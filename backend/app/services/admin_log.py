"""管理员操作审计：写日志（显式调用）+ 查询。"""
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import AdminActor
from app.models.admin_log import AdminLog

# ---- action 常量（集中定义，避免魔法字符串散落） ----
REPORT_HANDLE = "report.handle"
USER_FREEZE = "user.freeze"
USER_UNFREEZE = "user.unfreeze"
USER_ROLE = "user.role"
POST_STATUS = "post.status"
POST_BATCH = "post.batch_status"
POST_EDIT = "post.edit"
POST_PIN = "post.pin"
POST_FEATURED = "post.featured"
COMMENT_DELETE = "comment.delete"
COMMENT_STATUS = "comment.status"
PARTY_STATUS = "party.status"
ANNOUNCEMENT_SEND = "announcement.send"
BANNER_CREATE = "banner.create"
BANNER_UPDATE = "banner.update"
BANNER_DELETE = "banner.delete"
SENSITIVE_WORD_CREATE = "sensitive_word.create"
SENSITIVE_WORD_UPDATE = "sensitive_word.update"
SENSITIVE_WORD_DELETE = "sensitive_word.delete"
EXPORT_POSTS = "export.posts"
EXPORT_USERS = "export.users"
IMAGE_UPLOAD = "image.upload"
ADMIN_CREATE = "admin.create"
ADMIN_STATUS = "admin.status"
ADMIN_PASSWORD_RESET = "admin.password_reset"
TAG_CREATE = "tag.create"
TAG_DELETE = "tag.delete"
ACTIVITY_CREATE = "activity.create"
ACTIVITY_UPDATE = "activity.update"
ACTIVITY_DELETE = "activity.delete"
MAINTENANCE_CLEANUP = "maintenance.cleanup"


async def log_admin_action(
    db: AsyncSession,
    actor: AdminActor,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    """记录一条管理操作。只 add 不 commit：随调用方事务落库（失败可一起回滚）。"""
    db.add(AdminLog(
        admin_id=actor.id,
        admin_name=actor.display_name,
        source=actor.source,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail,
        ip=ip,
    ))


async def list_admin_logs(
    db: AsyncSession,
    *,
    action: str | None = None,
    admin_id: str | None = None,
    time_start: datetime | None = None,
    time_end: datetime | None = None,
    cursor: int | None = None,
    limit: int = 20,
    page: int | None = None,
    page_size: int = 20,
):
    """审计日志查询：动作/管理员/时间范围筛选，支持游标与页码分页。"""
    conditions = []
    if action:
        conditions.append(AdminLog.action == action)
    if admin_id:
        conditions.append(AdminLog.admin_id == admin_id)
    if time_start:
        conditions.append(AdminLog.created_at >= time_start)
    if time_end:
        conditions.append(AdminLog.created_at <= time_end)

    def _log_to_dict(log):
        return {
            "id": log.id,
            "admin_id": log.admin_id,
            "admin_name": log.admin_name,
            "source": log.source,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "detail": log.detail,
            "ip": log.ip,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    if page is not None:
        total = await db.scalar(
            select(func.count()).select_from(AdminLog).where(*conditions)
        ) or 0
        stmt = (
            select(AdminLog)
            .where(*conditions)
            .order_by(AdminLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [_log_to_dict(log) for log in rows], None, False, total

    if cursor:
        conditions.append(AdminLog.id < cursor)

    stmt = (
        select(AdminLog)
        .where(*conditions)
        .order_by(AdminLog.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]

    items = [_log_to_dict(log) for log in rows]
    next_cursor = rows[-1].id if has_more and rows else None
    return items, next_cursor, has_more
