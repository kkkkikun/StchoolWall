from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class AdminPasswordChangeRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class AdminAccountCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    nickname: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class AdminAccountStatusRequest(BaseModel):
    is_active: bool


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=100)
