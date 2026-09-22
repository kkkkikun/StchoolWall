from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    nickname: str
    real_name: str | None = None
    student_id: str | None = None
    wechat_id: str | None = None
    avatar_url: str | None = None
    banner_url: str | None = None
    bio: str | None = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=50)
    wechat_id: str | None = Field(None, max_length=50)
    avatar_url: str | None = Field(None, max_length=255)
    banner_url: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=200)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=64)
    new_password: str = Field(..., min_length=6, max_length=64)


class DeleteAccountRequest(BaseModel):
    """注销账号：网页账号需要密码确认；微信登录账号无密码可留空。"""
    password: str | None = Field(None, min_length=6, max_length=64)
