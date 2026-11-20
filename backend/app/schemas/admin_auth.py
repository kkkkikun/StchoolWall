from typing import Literal

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    totp_code: str | None = Field(None, min_length=6, max_length=6)
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)
    login_kind: Literal["admin", "owner"] | None = None


class AdminMfaSetupVerifyRequest(BaseModel):
    setup_token: str = Field(..., min_length=100, max_length=4096)
    totp_code: str = Field(..., min_length=6, max_length=6)


class AdminPasswordChangeRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class AdminAccountCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    nickname: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    role: Literal["admin", "owner"] = "admin"


class AdminAccountStatusRequest(BaseModel):
    is_active: bool


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=100)
