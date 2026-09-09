from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginResponse, VerifyRequest, WebLoginRequest, WxLoginRequest
from app.services.auth import dev_login, student_verify, web_login, wx_login
from app.utils.rate_limit import LOGIN_USER_RATE, check_rate_limit, clear_rate, get_rate, incr_rate

router = APIRouter()

# 网页登录按用户名失败退避（同管理台语义）
WEB_LOGIN_USER_RATE = LOGIN_USER_RATE


@router.post("/login")
async def login(body: WxLoginRequest, db: AsyncSession = Depends(get_db)):
    """微信静默登录"""
    return await wx_login(body.code, db)


@router.post("/dev-login")
async def dev_login_route(as_admin: bool = Query(False), db: AsyncSession = Depends(get_db)):
    """开发环境一键登录（双闸：development 环境 + .env 显式 DEV_LOGIN_ENABLED=true）。

    ?as_admin=true 登演示管理员（管理后台联调）。
    """
    if not (settings.ENVIRONMENT == "development" and settings.DEV_LOGIN_ENABLED):
        raise HTTPException(status_code=404, detail="Not Found")
    return await dev_login(db, as_admin=as_admin)


@router.post("/web-login")
async def web_login_route(
    body: WebLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """网页版登录（不存在即注册）。双限流：IP 10/min + 用户名失败退避 5/10min。"""
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"rl:web_login:ip:{client_ip}", max_requests=10, window_seconds=60)

    username_key = f"rl:web_login:user:{body.username}"
    max_fails, window = WEB_LOGIN_USER_RATE
    if await get_rate(username_key) >= max_fails:
        raise HTTPException(status_code=429, detail="失败次数过多，请稍后再试")

    result = await web_login(db, body.username, body.password)
    if result.get("code") == 401:
        await incr_rate(username_key, window)
        raise HTTPException(status_code=401, detail=result["message"])
    if result.get("code") == 403:
        raise HTTPException(status_code=403, detail=result["message"])
    await clear_rate(username_key)  # 成功清零
    return result


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

    # 未配置教务地址时明确 400（否则 httpx 相对 URL 500）
    if not settings.ZHENGFANG_BASE_URL:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="认证服务未配置，请联系管理员")

    result = await student_verify(user, body.student_id, body.password, db)

    if result.get("code") == 40901:
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail=result)

    return result
