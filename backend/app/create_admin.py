"""创建/重置管理后台账号的 CLI。

用法（backend 目录下）：
    python -m app.create_admin <username> [--nickname 昵称] [--reset]

密码交互输入（两次确认），绝不落在命令行参数或代码里。
"""
import asyncio
import getpass
import sys

from app.database import async_session
from app.services.admin_auth import create_or_reset_admin

MIN_PASSWORD_LEN = 8


def _read_password() -> str:
    while True:
        pwd = getpass.getpass("设置密码（至少 8 位）: ")
        if len(pwd) < MIN_PASSWORD_LEN:
            print(f"密码太短：至少 {MIN_PASSWORD_LEN} 位")
            continue
        pwd2 = getpass.getpass("再输入一次确认: ")
        if pwd != pwd2:
            print("两次输入不一致，请重试")
            continue
        return pwd


async def main() -> int:
    args = sys.argv[1:]
    reset = "--reset" in args
    positional = [a for a in args if not a.startswith("--")]
    nickname = None
    if "--nickname" in args:
        nickname = args[args.index("--nickname") + 1]

    if not positional:
        print(__doc__)
        return 1
    username = positional[0]

    password = _read_password()

    async with async_session() as db:
        admin, created = await create_or_reset_admin(
            db, username=username, nickname=nickname or "", password=password, reset=reset
        )
        action = "创建" if created else ("重置" if reset else "已存在（用 --reset 重置密码）")
        print(f"[OK] 管理员 {admin.username}（{admin.nickname}）{action}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
