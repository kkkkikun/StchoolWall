import base64
import hashlib
import hmac
import struct
import time

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from app.config import settings

def _fernet():
    try:
        return Fernet(settings.ADMIN_MFA_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "管理后台双重验证未配置") from None

def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()

def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise HTTPException(503, "双重验证配置不可用") from None

def totp_code(secret: str, counter: int) -> str:
    key = base64.b32decode(secret, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return f"{value % 1000000:06d}"

def verify_totp(encrypted: str, code: str, last_counter: int | None) -> int | None:
    if not code.isascii() or not code.isdigit() or len(code) != 6:
        return None
    secret = decrypt_secret(encrypted)
    counter = int(time.time() // 30)
    for candidate in (counter - 1, counter, counter + 1):
        if candidate > (last_counter if last_counter is not None else -1) and hmac.compare_digest(totp_code(secret, candidate), code):
            return candidate
    return None
