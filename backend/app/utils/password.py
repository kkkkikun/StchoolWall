"""密码哈希工具（bcrypt）。

不用 passlib：与 bcrypt>=4.1 不兼容（读 __about__ 报错）且已停更。
"""
import bcrypt

# 工作因子：登录场景的安全默认值
BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # 哈希串损坏等异常一律视为不匹配
        return False
