from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.schemas.user import ProfileResponse, ProfileUpdateRequest

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
        },
    }


@router.put("/profile")
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(require_role("student", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """更新用户资料 - 仅允许修改 nickname 和 wechat_id"""
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.wechat_id is not None:
        user.wechat_id = body.wechat_id
    await db.commit()
    return {"code": 0, "message": "success"}
