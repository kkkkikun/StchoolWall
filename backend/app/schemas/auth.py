from pydantic import BaseModel, Field


class WxLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="wx.login 获取的 code")


class VerifyRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=20, description="学号")
    password: str = Field(..., min_length=1, description="教务系统密码")


class UserInfoBrief(BaseModel):
    id: str
    nickname: str
    is_verified: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    role: str
    user_info: UserInfoBrief
