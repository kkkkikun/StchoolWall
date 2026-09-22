from pydantic import BaseModel, Field


class WxLoginRequest(BaseModel):
    code: str = Field(..., min_length=1, description="wx.login 获取的 code")


class VerifyRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=20, description="学号")
    password: str = Field(..., min_length=1, max_length=100, description="教务系统密码")


class WebLoginRequest(BaseModel):
    """网页版登录（不存在即注册）：昵称即用户名。"""
    username: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=6, max_length=64)


class MpLoginRequest(BaseModel):
    """公众号网页授权回调 code 登录。"""
    code: str = Field(..., min_length=1, max_length=512, description="公众号 OAuth 回调 code")


class UserInfoBrief(BaseModel):
    id: str
    nickname: str
    is_verified: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    role: str
    user_info: UserInfoBrief
