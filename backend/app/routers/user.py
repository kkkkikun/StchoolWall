from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
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


@router.put("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(require_role("student", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """更新用户资料（昵称/微信/头像/横幅/简介）"""
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.wechat_id is not None:
        user.wechat_id = body.wechat_id
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    if body.banner_url is not None:
        user.banner_url = body.banner_url
    if body.bio is not None:
        user.bio = body.bio
    await db.commit()
    return {"code": 0, "message": "success"}


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
    limit: int = Query(5, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Top 用户（按帖子获赞总数）；公开接口无需登录。"""
    items = await hot_users(db, limit)
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
