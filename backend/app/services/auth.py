import random
import string

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.utils.password import hash_password, verify_password
from app.utils.security import create_access_token
from app.utils.zhengfang import verify_student


def _generate_nickname() -> str:
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"鄂应学子_{code}"


async def wx_login(code: str, db: AsyncSession) -> dict:
    url = (
        f"https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={settings.WECHAT_APP_ID}"
        f"&secret={settings.WECHAT_APP_SECRET}"
        f"&js_code={code}"
        f"&grant_type=authorization_code"
    )
    async with httpx.AsyncClient(trust_env=False) as client:
        resp = await client.get(url, timeout=10)
        data = resp.json()

    openid = data.get("openid")
    if not openid:
        return {"code": 400, "message": "微信登录失败，请重试", "data": None}

    result = await db.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            openid=openid,
            nickname=_generate_nickname(),
            role="guest",
            is_verified=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {
        "code": 0,
        "message": "success",
        "data": {
            "access_token": token,
            "role": user.role,
            "user_info": {
                "id": str(user.id),
                "nickname": user.nickname,
                "is_verified": user.is_verified,
            },
        },
    }


async def dev_login(db: AsyncSession, as_admin: bool = False) -> dict:
    """开发环境一键登录（演示身份），仅 ENVIRONMENT=development 暴露路由。

    as_admin=True 登演示管理员（管理后台联调用）；默认演示学生。
    用户不存在时自动创建（管理员同样落 student_id/real_name，仅演示库使用）。
    """
    if as_admin:
        openid = "dev_demo_admin"
        defaults = dict(nickname="演示管理员", role="admin", student_id="2024ADMIN", real_name="演示管理员")
    else:
        openid = "dev_demo_student"
        defaults = dict(nickname="演示同学", role="student", student_id="2024DEV", real_name="演示同学")

    result = await db.execute(select(User).where(User.openid == openid))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(openid=openid, is_verified=True, **defaults)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {
        "code": 0,
        "message": "success",
        "data": {
            "access_token": token,
            "role": user.role,
            "user_info": {
                "id": str(user.id),
                "nickname": user.nickname,
                "is_verified": user.is_verified,
            },
        },
    }


async def student_verify(
    user: User, student_id: str, password: str, db: AsyncSession
) -> dict:
    if user.is_verified:
        return {"code": 400, "message": "你已完成学籍认证", "data": None}

    # Check if student_id already bound
    result = await db.execute(select(User).where(User.student_id == student_id))
    existing = result.scalar_one_or_none()
    if existing and existing.id != user.id:
        return {
            "code": 40901,
            "message": "该学号已被其他微信号绑定，请联系管理员申诉",
        }

    # Call zhengfang crawler
    result = await verify_student(student_id, password, settings.ZHENGFANG_BASE_URL)

    if result["status"] != "success":
        return {"code": 400, "message": result.get("msg", "认证失败"), "data": None}

    # Update user
    user.student_id = student_id
    user.real_name = result.get("real_name")
    user.is_verified = True
    user.role = "student"
    await db.commit()

    # Issue upgraded token
    token = create_access_token({"sub": str(user.id), "role": "student"})
    return {
        "code": 0,
        "message": "认证成功",
        "data": {"access_token": token, "role": "student"},
    }


async def web_login(db: AsyncSession, username: str, password: str) -> dict:
    """网页版登录：账号不存在即注册（昵称即用户名），存在则校验密码。

    - openid 命名空间 web:{username}，与微信用户互不冲突
    - role=guest：网页注册仅可浏览/签到，发帖互动需走学籍认证升级为 student
    - 冻结用户拒登；密码 bcrypt 存储，绝不落明文
    """
    openid = f"web:{username}"
    user = (await db.execute(select(User).where(User.openid == openid))).scalar_one_or_none()

    if user is None:
        user = User(
            openid=openid,
            nickname=username,
            role="guest",
            is_verified=False,
            web_password_hash=hash_password(password),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        if user.status == 0:
            return {"code": 403, "message": "账号已被冻结", "data": None}
        if not user.web_password_hash or not verify_password(password, user.web_password_hash):
            return {"code": 401, "message": "用户名或密码错误", "data": None}

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {
        "code": 0,
        "message": "success",
        "data": {
            "access_token": token,
            "role": user.role,
            "user_info": {
                "id": str(user.id),
                "nickname": user.nickname,
                "is_verified": user.is_verified,
            },
        },
    }
