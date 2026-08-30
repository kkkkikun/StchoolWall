from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginResponse, VerifyRequest, WxLoginRequest
from app.services.auth import dev_login, student_verify, wx_login
from app.utils.rate_limit import check_rate_limit

router = APIRouter()


@router.post("/login")
async def login(body: WxLoginRequest, db: AsyncSession = Depends(get_db)):
    """微信静默登录"""
    return await wx_login(body.code, db)


@router.post("/dev-login")
async def dev_login_route(as_admin: bool = Query(False), db: AsyncSession = Depends(get_db)):
    """开发环境一键登录（仅 development 暴露，用于 H5 预览联调）。

    ?as_admin=true 登演示管理员（管理后台联调）。
    """
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=404, detail="Not Found")
    return await dev_login(db, as_admin=as_admin)


@router.post("/verify")
async def verify(
    body: VerifyRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """学籍认证绑定 - 需登录，含限流"""
    # IP 限流: 10次/分钟
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"rl:ip:{client_ip}", max_requests=10, window_seconds=60)

    # OpenID 限流: 5次/10分钟
    await check_rate_limit(f"rl:openid:{user.openid}", max_requests=5, window_seconds=600)

    result = await student_verify(user, body.student_id, body.password, db)

    if result.get("code") == 40901:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=result)

    return result
