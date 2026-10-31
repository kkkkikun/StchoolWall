"""Run interactively on a trusted operator terminal to enroll/reset an authenticator."""
import argparse
import asyncio
import base64
import getpass
import secrets
from urllib.parse import quote
from sqlalchemy import select
from app.database import async_session
from app.models.admin_user import AdminUser
from app.utils.mfa import encrypt_secret, verify_totp

async def enroll(username):
    async with async_session() as db:
        admin = (await db.execute(select(AdminUser).where(AdminUser.username == username).with_for_update())).scalar_one_or_none()
        if not admin:
            raise SystemExit("管理员不存在")
        secret = base64.b32encode(secrets.token_bytes(20)).decode()
        encrypted = encrypt_secret(secret)
        print("在可信设备验证器中添加以下配置（不要保存到日志或聊天）：")
        print("otpauth://totp/" + quote("SchoolWall:" + username) + "?secret=" + secret + "&issuer=SchoolWall")
        code = getpass.getpass("输入验证器当前六位码：")
        if verify_totp(encrypted, code, None) is None:
            raise SystemExit("验证失败，未保存任何更改")
        admin.mfa_secret_encrypted = encrypted
        admin.mfa_last_counter = None
        admin.pwd_version += 1
        await db.commit()
        print("双重验证已启用，已有管理令牌已失效。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    asyncio.run(enroll(args.username))
