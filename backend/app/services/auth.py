import random
import string

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
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
