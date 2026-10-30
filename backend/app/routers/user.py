from app.services.runtime_controls import require_publishing
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.jobs import enqueue_job
from app.services.media import get_owned_media
from app.utils.rate_limit import check_rate_limit
from app.dependencies import get_current_user, get_optional_user, require_role
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, DeleteAccountRequest, ProfileResponse, ProfileUpdateRequest
from app.services.checkin import check_in, checkin_status
from app.services.profile import change_password, delete_account
from app.services.ranking import hot_users

router = APIRouter()


@router.get("/profile", response_model=dict)
async def get_profile(user: User = Depends(require_role("student", "admin"))):
    """获取个人资料"""
    return {
        "code": 0,
        "data": {
            "nickname": user.nickname,
            "real_name": user.real_name,
            "student_id": user.student_id,
            "wechat_id": user.wechat_id,
            "avatar_url": user.avatar_url,
            "banner_url": user.banner_url,
            "bio": user.bio,
            "is_verified": user.is_verified,
            "role": user.role,
        },
    }


@router.put("/profile", dependencies=[Depends(require_publishing)])
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(require_role("student", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Profile changes become public only after moderation."""
    await check_rate_limit(f"rl:u:{user.id}:profile", 10, 3600)
    updates = {}
    media = {}
    for key in ("nickname", "bio", "wechat_id"):
        value = getattr(body, key, None)
        if value is not None:
            updates[key] = value
    for url_field, id_field, purpose in (
        ("avatar_url", "avatar_media_id", "avatars"),
        ("banner_url", "banner_media_id", "banners"),
    ):
        media_id = getattr(body, id_field, None)
        raw_url = getattr(body, url_field, None)
        if media_id:
            asset = await get_owned_media(db, media_id, user.id)
            if not asset or asset.purpose != purpose or asset.status in {"rejected", "deleted"}:
                raise HTTPException(status_code=400, detail="图片不存在、用途不符或已被拒绝")
            if asset.entity_type not in (None, "profile"):
                raise HTTPException(status_code=400, detail="图片已用于其他内容")
            asset.entity_type = "profile"
            media[url_field] = str(media_id)
        elif raw_url is not None and raw_url != getattr(user, url_field):
            if settings.ENVIRONMENT == "production" and raw_url:
                raise HTTPException(status_code=400, detail="头像和横幅请使用 media_id")
            updates[url_field] = raw_url
    if not updates and not media:
        return {"code": 0, "message": "success"}
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    payload = {"user_id": str(user.id), "expected_updated_at": user.updated_at.isoformat(),
               "updates": updates, "media": media}
    job_id = await enqueue_job(db, "moderate_profile", payload, f"profile:{user.id}:{uuid.uuid4()}")
    await db.commit()
    return {"code": 0, "message": "资料已提交审核", "data": {"job_id": str(job_id), "status": "pending"}}



@router.put("/password")
async def change_password_route(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改网页账号密码。"""
    try:
        await change_password(db, user, body.old_password, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "密码已更新"}


@router.post("/account/deactivate")
async def deactivate_account_route(
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """注销账号：软删除并清理隐私字段。"""
    try:
        await delete_account(db, user, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "message": "账号已注销"}


# ---- 热门用户榜（公开，消息页横滑） ----


@router.get("/hot-ranking")
async def get_hot_ranking(
    viewer: User | None = Depends(get_optional_user),
    limit: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Top 用户（按帖子获赞总数）；公开接口无需登录。"""
    items = await hot_users(db, limit, viewer)
    return {"code": 0, "data": {"items": items}}


# ---- 签到（游客也可签：留存工具；收益规则定稿后再收紧角色） ----


@router.post("/checkin")
async def do_checkin(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """每日签到（上海自然日）：返回是否重复、当前连签天数。"""
    result = await check_in(db, user)
    return {
        "code": 0,
        "message": "今日已签过" if result["already"] else "签到成功",
        "data": {
            "already": result["already"],
            "streak_days": result["streak_days"],
            "today": result["today"].isoformat(),
        },
    }


@router.get("/checkin/status")
async def get_checkin_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """签到状态：今日已签/连签/本月/累计。"""
    data = await checkin_status(db, user)
    data["today"] = data["today"].isoformat()
    return {"code": 0, "data": data}
