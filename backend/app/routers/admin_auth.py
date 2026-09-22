"""管理后台（console）认证路由：登录 / 当前账号 / 改密。"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import AdminActor, require_admin_console
from app.schemas.admin_auth import (
    AdminAccountCreateRequest,
    AdminAccountStatusRequest,
    AdminLoginRequest,
    AdminPasswordChangeRequest,
    AdminPasswordResetRequest,
)
from app.services.admin_auth import (
    authenticate_admin,
    change_admin_password,
    create_admin_user,
    get_admin_by_id,
    issue_console_token,
    list_admin_users,
    reset_admin_password,
    set_admin_active,
)
from app.services import admin_log
from app.services.admin_log import log_admin_action
from app.utils.rate_limit import LOGIN_USER_RATE, check_rate_limit, clear_rate, get_rate, incr_rate

router = APIRouter()

# 登录防爆破：每 IP 每分钟 10 次
LOGIN_RATE_MAX = 10
LOGIN_RATE_WINDOW = 60


@router.post("/auth/login")
async def admin_login(body: AdminLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """账号密码登录（IP 限流 + 按用户名失败退避），返回 console 专用 token。"""
    ip = request.client.host if request.client else "unknown"
    # 超限直接抛 429
    await check_rate_limit(f"rl:admin_login:ip:{ip}", LOGIN_RATE_MAX, LOGIN_RATE_WINDOW)

    # 按用户名退避：连续失败超阈值后，窗口内正确密码也拒（防换 IP 在线爆破）
    username_key = f"rl:admin_login:user:{body.username}"
    max_fails, window = LOGIN_USER_RATE
    if await get_rate(username_key) >= max_fails:
        raise HTTPException(status_code=429, detail="失败次数过多，请稍后再试")

    admin = await authenticate_admin(db, body.username, body.password)
    if admin is None:
        await incr_rate(username_key, window)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    await clear_rate(username_key)  # 成功清零

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


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---- 管理后台账号管理 ----


@router.get("/admins")
async def list_admin_accounts(
    q: str | None = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """管理后台账号列表（仅 admin）。"""
    items, total = await list_admin_users(db, q=q, page=page, page_size=page_size)
    return {"code": 0, "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.post("/admins")
async def create_admin_account(
    body: AdminAccountCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """新建管理后台账号（仅 admin）。"""
    admin, error = await create_admin_user(db, body.username, body.nickname, body.password)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await log_admin_action(db, actor, admin_log.ADMIN_CREATE,
                           target_type="admin_user", target_id=admin.id,
                           detail={"username": admin.username, "nickname": admin.nickname},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "创建成功",
            "data": {"id": str(admin.id), "username": admin.username, "nickname": admin.nickname}}


@router.put("/admins/{admin_id}/status")
async def update_admin_account_status(
    admin_id: str,
    body: AdminAccountStatusRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """启用/停用管理后台账号（仅 admin）；停用会立即让对应 token 失效。"""
    admin, error = await set_admin_active(db, admin_id, body.is_active, actor_id=actor.id)
    if error == "管理员不存在":
        raise HTTPException(status_code=404, detail=error)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await log_admin_action(db, actor, admin_log.ADMIN_STATUS,
                           target_type="admin_user", target_id=admin_id,
                           detail={"is_active": body.is_active},
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "已启用" if body.is_active else "已停用",
            "data": {"id": str(admin.id), "is_active": admin.is_active}}


@router.put("/admins/{admin_id}/password")
async def reset_admin_account_password(
    admin_id: str,
    body: AdminPasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    """强制重置其他管理员密码（仅 admin）；目标账号旧 token 全部失效。"""
    admin, error = await reset_admin_password(db, admin_id, body.new_password, actor_id=actor.id)
    if error == "管理员不存在":
        raise HTTPException(status_code=404, detail=error)
    if error:
        raise HTTPException(status_code=400, detail=error)
    await log_admin_action(db, actor, admin_log.ADMIN_PASSWORD_RESET,
                           target_type="admin_user", target_id=admin_id,
                           ip=_client_ip(request))
    await db.commit()
    return {"code": 0, "message": "密码已重置", "data": {"id": str(admin.id)}}
