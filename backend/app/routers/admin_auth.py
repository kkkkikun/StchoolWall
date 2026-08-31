"""管理后台（console）认证路由：登录 / 当前账号 / 改密。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.schemas.admin_auth import AdminLoginRequest, AdminPasswordChangeRequest
from app.services.admin_auth import (
    authenticate_admin,
    change_admin_password,
    get_admin_by_id,
    issue_console_token,
)
from app.utils.rate_limit import check_rate_limit

router = APIRouter()

# 登录防爆破：每 IP 每分钟 10 次
LOGIN_RATE_MAX = 10
LOGIN_RATE_WINDOW = 60


@router.post("/auth/login")
async def admin_login(body: AdminLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """账号密码登录（限流防爆破），返回 console 专用 token。"""
    ip = request.client.host if request.client else "unknown"
    # 超限直接抛 429
    await check_rate_limit(f"rl:admin_login:ip:{ip}", LOGIN_RATE_MAX, LOGIN_RATE_WINDOW)

    admin = await authenticate_admin(db, body.username, body.password)
    if admin is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    return {
        "code": 0,
        "message": "登录成功",
        "data": {
            "access_token": issue_console_token(admin),
            "admin": {"id": str(admin.id), "username": admin.username, "nickname": admin.nickname},
        },
    }


@router.get("/auth/me")
async def admin_me(actor: AdminActor = Depends(require_admin_console)):
    """当前登录的管理员信息。"""
    return {"code": 0, "data": {"id": actor.id, "display_name": actor.display_name, "source": actor.source}}


@router.put("/auth/password")
async def admin_change_password(
    body: AdminPasswordChangeRequest,
    actor: AdminActor = Depends(require_admin_console),
    db: AsyncSession = Depends(get_db),
):
    """修改密码；成功后 pwd_version+1，所有旧 console token 失效（需重新登录）。"""
    # 只有 console 体系能改密（legacy 小程序管理员无密码概念）
    if actor.source != "console":
        raise HTTPException(status_code=403, detail="请使用管理后台账号登录后修改密码")

    admin = await get_admin_by_id(db, actor.id)
    if admin is None:
        raise HTTPException(status_code=401, detail="账号不存在")

    ok = await change_admin_password(db, admin, body.old_password, body.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="原密码错误")

    return {"code": 0, "message": "密码已修改，请重新登录"}
